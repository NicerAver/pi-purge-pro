const t = require('@babel/types')
const traverse = require('@babel/traverse').default

function getKey(node) {
  if (t.isIdentifier(node)) return node.name
  if (t.isStringLiteral(node)) return node.value
  return null
}

function clone(node) {
  return t.cloneNode(node, true)
}

function replaceParams(expression, params, args) {
  const map = new Map()
  params.forEach((param, index) => {
    if (t.isIdentifier(param) && args[index]) {
      map.set(param.name, clone(args[index]))
    }
  })

  const file = t.file(t.program([t.expressionStatement(clone(expression))]))
  traverse(file, {
    ReferencedIdentifier(path) {
      const replacement = map.get(path.node.name)
      if (replacement) path.replaceWith(clone(replacement))
    }
  })
  return file.program.body[0].expression
}

function getSimpleReturnExpression(value) {
  if (!t.isFunctionExpression(value) && !t.isArrowFunctionExpression(value)) return null
  if (!t.isBlockStatement(value.body) || value.body.body.length !== 1) return null
  const onlyStatement = value.body.body[0]
  if (!t.isReturnStatement(onlyStatement) || !onlyStatement.argument) return null
  return onlyStatement.argument
}

function isSimpleIdentifierList(params) {
  const names = new Set()
  for (const param of params) {
    if (!t.isIdentifier(param) || names.has(param.name)) return false
    names.add(param.name)
  }
  return true
}

function usesUnsafeNodes(expression) {
  let unsafe = false
  function scan(node) {
    if (!node || unsafe) return
    if (Array.isArray(node)) {
      node.forEach(scan)
      return
    }
    if (typeof node !== 'object') return
    if (
      t.isThisExpression(node) ||
      t.isSuper(node) ||
      t.isAssignmentExpression(node) ||
      t.isUpdateExpression(node) ||
      t.isAwaitExpression(node) ||
      t.isYieldExpression(node) ||
      t.isMetaProperty(node) ||
      t.isFunction(node) ||
      (t.isIdentifier(node, { name: 'arguments' }))
    ) {
      unsafe = true
      return
    }
    for (const key of t.VISITOR_KEYS[node.type] || []) {
      scan(node[key])
    }
  }
  scan(expression)
  return unsafe
}

function hasFreeReferences(expression, params) {
  const parameterNames = new Set(params.map((param) => param.name))
  const file = t.file(t.program([t.expressionStatement(clone(expression))]))
  let found = false
  traverse(file, {
    ReferencedIdentifier(path) {
      if (!parameterNames.has(path.node.name)) {
        found = true
        path.stop()
      }
    }
  })
  return found
}

function isSafeInlineArgument(node) {
  if (
    t.isStringLiteral(node) || t.isNumericLiteral(node) ||
    t.isBooleanLiteral(node) || t.isNullLiteral(node) ||
    t.isBigIntLiteral(node)
  ) {
    return true
  }
  return false
}

function buildSafeInlineExpression(value, args) {
  const returnExpr = getSimpleReturnExpression(value)
  if (!returnExpr) return null
  if (!isSimpleIdentifierList(value.params)) return null
  if (usesUnsafeNodes(returnExpr)) return null
  if (hasFreeReferences(returnExpr, value.params)) return null
  if (args.length !== value.params.length) return null
  if (!args.every((arg) => t.isExpression(arg) && isSafeInlineArgument(arg))) return null

  if (t.isBinaryExpression(returnExpr) || t.isLogicalExpression(returnExpr)) {
    return replaceParams(returnExpr, value.params, args)
  }

  if (t.isCallExpression(returnExpr) && t.isIdentifier(returnExpr.callee)) {
    return replaceParams(returnExpr, value.params, args)
  }

  if (
    t.isMemberExpression(returnExpr) &&
    t.isIdentifier(returnExpr.object) &&
    (t.isIdentifier(returnExpr.property) || t.isStringLiteral(returnExpr.property) || t.isNumericLiteral(returnExpr.property))
  ) {
    return replaceParams(returnExpr, value.params, args)
  }

  if (t.isConditionalExpression(returnExpr)) {
    return replaceParams(returnExpr, value.params, args)
  }

  return null
}

module.exports = {
  Program: {
    enter(path, state) {
      const dispatchTables = new Map()
      let hasDirectEval = false

      path.traverse({
        CallExpression(innerPath) {
          if (innerPath.get('callee').isIdentifier({ name: 'eval' })) hasDirectEval = true
        }
      })
      if (hasDirectEval) {
        state.dispatchTables = dispatchTables
        return
      }

      path.traverse({
        VariableDeclarator(innerPath) {
          const { id, init } = innerPath.node
          if (!t.isIdentifier(id) || !t.isObjectExpression(init)) return
          const binding = innerPath.scope.getBinding(id.name)
          if (!binding || !binding.constant) return
          const readOnly = binding.referencePaths.every((reference) => {
            const member = reference.parentPath
            if (!member?.isMemberExpression() || member.node.object !== reference.node) return false
            const use = member.parentPath
            if (use?.isAssignmentExpression() && use.node.left === member.node) return false
            if (use?.isUpdateExpression() || (use?.isUnaryExpression({ operator: 'delete' }))) return false
            return true
          })
          if (!readOnly) return

          const table = new Map()
          let valid = true
          for (const property of init.properties) {
            if (!t.isObjectProperty(property)) {
              valid = false
              break
            }
            if (property.computed && !t.isStringLiteral(property.key) && !t.isNumericLiteral(property.key)) {
              valid = false
              break
            }
            const key = getKey(property.key)
            if (!key || key === '__proto__') {
              valid = false
              break
            }
            table.set(key, property.value)
          }
          if (valid && table.size > 0) {
            dispatchTables.set(binding, table)
          }
        }
      })

      state.dispatchTables = dispatchTables
    }
  },

  MemberExpression(path, state) {
    if (!path.isReferenced()) return
    if (!path.node.computed) return
    if (!t.isIdentifier(path.node.object)) return
    if (!t.isStringLiteral(path.node.property)) return

    const binding = path.scope.getBinding(path.node.object.name)
    const table = binding && state.dispatchTables?.get(binding)
    if (!table) return
    if (binding.path.node.start == null || path.node.start == null || binding.path.node.start >= path.node.start) return
    const value = table.get(path.node.property.value)
    if (!value) return

    if (t.isStringLiteral(value) || t.isNumericLiteral(value) || t.isBooleanLiteral(value) || t.isNullLiteral(value)) {
      path.replaceWith(clone(value))
    }
  },

  CallExpression(path, state) {
    const callee = path.node.callee
    if (!t.isMemberExpression(callee) || !callee.computed) return
    if (!t.isIdentifier(callee.object) || !t.isStringLiteral(callee.property)) return

    const binding = path.scope.getBinding(callee.object.name)
    const table = binding && state.dispatchTables?.get(binding)
    if (!table) return
    if (binding.path.node.start == null || path.node.start == null || binding.path.node.start >= path.node.start) return
    const value = table.get(callee.property.value)
    if (!value) return

    const replaced = buildSafeInlineExpression(value, path.node.arguments)
    if (!replaced) return
    path.replaceWith(replaced)
  }
}
