const { applyVisitors } = require('../lib/core')

const deleteExtra = require('../visitors/delete-extra')
const foldBinary = require('../visitors/fold-binary')
const foldBoolean = require('../visitors/fold-boolean')
const mergeStrings = require('../visitors/merge-strings')
const normalizeMember = require('../visitors/normalize-member')
const splitSequence = require('../visitors/split-sequence')
const constantIf = require('../visitors/constant-if')
const removeEmpty = require('../visitors/remove-empty')

module.exports = function runCommon(ast, options = {}) {
  return applyVisitors(ast, [
    { name: 'delete-extra', visitor: deleteExtra },
    { name: 'fold-binary', visitor: foldBinary },
    { name: 'fold-boolean', visitor: foldBoolean },
    { name: 'merge-strings', visitor: mergeStrings },
    { name: 'normalize-member', visitor: normalizeMember },
    { name: 'split-sequence', visitor: splitSequence },
    { name: 'constant-if', visitor: constantIf },
    { name: 'remove-empty', visitor: removeEmpty }
  ], options)
}
