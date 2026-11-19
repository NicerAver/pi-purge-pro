const { applyVisitors } = require('../lib/core')
const runCommon = require('./common')

const inlineDispatcher = require('../visitors/inline-dispatcher')
const whileSwitchUnpack = require('../visitors/while-switch-unpack')
const normalizeMember = require('../visitors/normalize-member')

module.exports = function runObfuscator(ast, options = {}) {
  const current = applyVisitors(ast, [
    { name: 'inline-dispatcher', visitor: inlineDispatcher },
    { name: 'while-switch-unpack', visitor: whileSwitchUnpack },
    { name: 'normalize-member', visitor: normalizeMember }
  ], options)
  return runCommon(current, options)
}
