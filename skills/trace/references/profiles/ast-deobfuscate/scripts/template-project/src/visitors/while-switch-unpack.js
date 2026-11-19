const t = require('@babel/types')

function isForeverLoop(test) {
  return (
    t.isBooleanLiteral(test, { value: true }) ||
    (t.isUnaryExpression(test, { operator: '!' }) && t.isNumericLiteral(test.argument, { value: 0 }))
  )
}

function getOrderFromInit(init) {
  if (t.isArrayExpression(init)) {
    const values = []
    for (const element of init.elements) {
      if (!element) return null
      if (!t.isStringLiteral(element) && !t.isNumericLiteral(element)) return null
      values.push(String(element.value))
    }
    return values
  }

  return null
}

function getCaseKey(test) {
  if (t.isStringLiteral(test) || t.isNumericLiteral(test)) {
    return String(test.value)
  }
  return null
}

function containsEscapingControl(node) {
  if (!node) return false
  if (t.isBreakStatement(node) || t.isContinueStatement(node)) return true
  if (t.isFunction(node)) return false
  for (const key of t.VISITOR_KEYS[node.type] || []) {
    const child = node[key]
    if (Array.isArray(child)) {
      if (child.some(containsEscapingControl)) return true
    } else if (containsEscapingControl(child)) {
      return true
    }
  }
  return false
}

function getSafeCaseChunk(statements) {
  if (statements.length === 0) return null
  const out = statements.map((statement) => t.cloneNode(statement, true))
  const last = out[out.length - 1]
  if (out.slice(0, -1).some(containsEscapingControl)) return null
  if (t.isContinueStatement(last) && !last.label) {
    out.pop()
    return { statements: out, terminal: false }
  }
  if (t.isReturnStatement(last) || t.isThrowStatement(last)) {
    return { statements: out, terminal: true }
  }
  return null
}

function getDiscriminantInfo(discriminant) {
  if (!t.isMemberExpression(discriminant) || !t.isIdentifier(discriminant.object)) {
    return null
  }

  const orderName = discriminant.object.name
  let indexName = null

  if (
    t.isUpdateExpression(discriminant.property, { operator: '++', prefix: false }) &&
    t.isIdentifier(discriminant.property.argument)
  ) {
    indexName = discriminant.property.argument.name
  }

  if (!indexName) return null
  return { orderName, indexName }
}

function isInside(candidate, ancestor) {
  for (let current = candidate; current; current = current.parentPath) {
    if (current === ancestor) return true
  }
  return false
}

function hasOutsideReferences(binding, loopPath) {
  return binding.referencePaths.some((reference) => !isInside(reference, loopPath))
}

function hasOnlyReference(binding, node) {
  return binding.referencePaths.length === 1 && binding.referencePaths[0].node === node
}

function declarationDominates(binding, loopPath) {
  const declaration = binding.path.parentPath
  return (
    declaration.isVariableDeclaration() &&
    declaration.parentPath === loopPath.parentPath &&
    Number.isInteger(declaration.key) &&
    Number.isInteger(loopPath.key) &&
    declaration.key < loopPath.key
  )
}

function containsDynamicScopeAccess(node) {
  if (!node) return false
  if (t.isWithStatement(node)) return true
  if (t.isCallExpression(node) && t.isIdentifier(node.callee, { name: 'eval' })) return true
  if (t.isFunction(node)) return false
  for (const key of t.VISITOR_KEYS[node.type] || []) {
    const child = node[key]
    if (Array.isArray(child)) {
      if (child.some(containsDynamicScopeAccess)) return true
    } else if (containsDynamicScopeAccess(child)) {
      return true
    }
  }
  return false
}

function buildCaseMap(cases) {
  const caseMap = new Map()
  let inheritedConsequent = null

  for (let index = cases.length - 1; index >= 0; index -= 1) {
    const switchCase = cases[index]
    const key = getCaseKey(switchCase.test)
    if (key === null) continue

    if (switchCase.consequent.length === 0 && inheritedConsequent) {
      caseMap.set(key, inheritedConsequent)
      continue
    }

    inheritedConsequent = switchCase
    caseMap.set(key, switchCase)
  }

  return caseMap
}

module.exports = {
  WhileStatement: {
    exit(path) {
      if (!isForeverLoop(path.node.test)) return
      if (containsDynamicScopeAccess(path.node)) return

      const body = path.node.body
      if (!t.isBlockStatement(body) || body.body.length === 0) return

      const first = body.body[0]
      const second = body.body[1]
      if (!t.isSwitchStatement(first)) return
      if (body.body.length !== 2 || !t.isBreakStatement(second) || second.label) return

      const discInfo = getDiscriminantInfo(first.discriminant)
      if (!discInfo) return

      const orderBinding = path.scope.getBinding(discInfo.orderName)
      if (!orderBinding || !orderBinding.path.isVariableDeclarator() || !orderBinding.constant) return
      const indexBinding = path.scope.getBinding(discInfo.indexName)
      if (!indexBinding || !indexBinding.path.isVariableDeclarator()) return
      if (!declarationDominates(orderBinding, path) || !declarationDominates(indexBinding, path)) return
      if (hasOutsideReferences(orderBinding, path) || hasOutsideReferences(indexBinding, path)) return
      if (!hasOnlyReference(orderBinding, first.discriminant.object)) return
      if (!hasOnlyReference(indexBinding, first.discriminant.property.argument)) return
      if (!t.isNumericLiteral(indexBinding.path.node.init, { value: 0 })) return
      if (indexBinding.constantViolations.some((violation) => violation.node !== first.discriminant.property)) return

      const order = getOrderFromInit(orderBinding.path.node.init)
      if (!order || order.length === 0) return
      if (first.cases.some((switchCase) => switchCase.test == null || getCaseKey(switchCase.test) === null)) return

      const caseMap = buildCaseMap(first.cases)

      const flattened = []
      for (const key of order) {
        const switchCase = caseMap.get(String(key))
        if (!switchCase) return

        const chunk = getSafeCaseChunk(switchCase.consequent)
        if (!chunk) return
        flattened.push(t.blockStatement(chunk.statements))
        if (chunk.terminal) break
      }

      if (flattened.length === 0) return

      const scope = path.scope
      path.replaceWith(t.blockStatement(flattened))
      scope.crawl()
    }
  }
}
