module.exports = {
  StringLiteral(path) {
    if (path.parentPath.isExpressionStatement()) return
    delete path.node.extra
  },
  NumericLiteral(path) {
    delete path.node.extra
  }
}
