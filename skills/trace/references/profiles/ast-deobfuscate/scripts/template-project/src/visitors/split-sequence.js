const t = require('@babel/types')

module.exports = {
  ExpressionStatement(path) {
    if (!t.isSequenceExpression(path.node.expression)) return
    if (path.node.expression.expressions.some((expression) => t.isStringLiteral(expression))) return
    path.replaceWithMultiple(path.node.expression.expressions.map((expr) => t.expressionStatement(expr)))
  }
}
