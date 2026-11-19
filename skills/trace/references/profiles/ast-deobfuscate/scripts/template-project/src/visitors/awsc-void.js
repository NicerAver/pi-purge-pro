const t = require('@babel/types')

function canDiscard(node) {
  return (
    t.isStringLiteral(node) || t.isNumericLiteral(node) ||
    t.isBooleanLiteral(node) || t.isNullLiteral(node) ||
    t.isBigIntLiteral(node) || t.isFunctionExpression(node) ||
    t.isArrowFunctionExpression(node)
  )
}

module.exports = {
  UnaryExpression(path) {
    if (path.node.operator !== 'void') return
    if (path.scope.hasBinding('undefined')) return

    const argument = path.node.argument
    const replacement = canDiscard(argument)
      ? t.identifier('undefined')
      : t.sequenceExpression([t.cloneNode(argument, true), t.identifier('undefined')])
    path.replaceWith(replacement)
  }
}
