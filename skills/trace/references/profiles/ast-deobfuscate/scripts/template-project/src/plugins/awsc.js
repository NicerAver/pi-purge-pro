const { applyVisitors } = require('../lib/core')
const runCommon = require('./common')

const awscVoid = require('../visitors/awsc-void')
const awscLogicalToIf = require('../visitors/awsc-logical-to-if')
const awscConditionalToIf = require('../visitors/awsc-conditional-to-if')
const awscNormalizeBlocks = require('../visitors/awsc-normalize-blocks')

module.exports = function runAwsc(ast, options = {}) {
  const current = applyVisitors(ast, [
    { name: 'awsc-void', visitor: awscVoid },
    { name: 'awsc-conditional-to-if', visitor: awscConditionalToIf },
    { name: 'awsc-logical-to-if', visitor: awscLogicalToIf },
    { name: 'awsc-normalize-blocks', visitor: awscNormalizeBlocks }
  ], options)
  return runCommon(current, options)
}
