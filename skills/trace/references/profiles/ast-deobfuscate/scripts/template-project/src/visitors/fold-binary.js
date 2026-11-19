const t = require('@babel/types')

function isPrimitiveLiteral(node) {
  return (
    t.isStringLiteral(node) || t.isNumericLiteral(node) ||
    t.isBooleanLiteral(node) || t.isNullLiteral(node) ||
    t.isBigIntLiteral(node)
  )
}

module.exports = {
  BinaryExpression: {
    exit(path) {
      if (!isPrimitiveLiteral(path.node.left) || !isPrimitiveLiteral(path.node.right)) return
      const evaluation = path.evaluate()
      if (!evaluation.confident) return
      if (typeof evaluation.value === 'function') return
      path.replaceWith(t.valueToNode(evaluation.value))
    }
  }
}
