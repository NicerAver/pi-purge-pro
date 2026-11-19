const runCommon = require('./common')

module.exports = function runSojson(ast, options = {}) {
  // Calls can depend on mutable globals or decoder state. Keep them intact and
  // use instrumentation/external isolation instead of evaluating them here.
  return runCommon(ast, options)
}
