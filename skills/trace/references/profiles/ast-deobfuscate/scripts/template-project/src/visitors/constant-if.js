const t = require('@babel/types')

function literalTruthiness(node) {
  if (t.isBooleanLiteral(node) || t.isNumericLiteral(node) || t.isStringLiteral(node)) {
    return Boolean(node.value)
  }
  if (t.isNullLiteral(node)) return false
  if (t.isBigIntLiteral(node)) return node.value !== '0'
  return null
}

function containsHoistedDeclaration(node) {
  if (!node) return false
  if (t.isVariableDeclaration(node, { kind: 'var' }) || t.isFunctionDeclaration(node)) return true
  if (t.isFunction(node)) return false
  for (const key of t.VISITOR_KEYS[node.type] || []) {
    const child = node[key]
    if (Array.isArray(child)) {
      if (child.some(containsHoistedDeclaration)) return true
    } else if (containsHoistedDeclaration(child)) {
      return true
    }
  }
  return false
}

module.exports = {
  IfStatement(path) {
    const truthiness = literalTruthiness(path.node.test)
    if (truthiness === null) return
    if (containsHoistedDeclaration(path.node.consequent) || containsHoistedDeclaration(path.node.alternate)) return
    if (truthiness) {
      path.replaceWith(t.cloneNode(path.node.consequent, true))
      return
    }
    if (!path.node.alternate) {
      path.remove()
      return
    }
    path.replaceWith(t.cloneNode(path.node.alternate, true))
  }
}
