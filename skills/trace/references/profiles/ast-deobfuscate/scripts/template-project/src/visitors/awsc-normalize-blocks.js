const t = require('@babel/types')

module.exports = {
  IfStatement(path) {
    if (!t.isBlockStatement(path.node.consequent) && !t.isFunctionDeclaration(path.node.consequent)) {
      path.node.consequent = t.blockStatement([path.node.consequent])
    }
    if (
      path.node.alternate && !t.isBlockStatement(path.node.alternate) &&
      !t.isIfStatement(path.node.alternate) && !t.isFunctionDeclaration(path.node.alternate)
    ) {
      path.node.alternate = t.blockStatement([path.node.alternate])
    }
  }
}
