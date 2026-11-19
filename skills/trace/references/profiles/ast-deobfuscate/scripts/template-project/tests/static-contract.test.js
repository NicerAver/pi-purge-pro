const assert = require('assert')
const fs = require('fs')
const path = require('path')
const { execFileSync } = require('child_process')


const root = path.resolve(__dirname, '..')
const src = path.join(root, 'src')
const files = []

function walk(directory) {
  for (const name of fs.readdirSync(directory)) {
    const file = path.join(directory, name)
    if (fs.statSync(file).isDirectory()) walk(file)
    else if (file.endsWith('.js')) files.push(file)
  }
}

walk(src)
for (const file of files) {
  execFileSync(process.execPath, ['--check', file], { stdio: 'pipe' })
}

const sojson = fs.readFileSync(path.join(src, 'plugins', 'sojson.js'), 'utf8')
const core = fs.readFileSync(path.join(src, 'lib', 'core.js'), 'utf8')
const main = fs.readFileSync(path.join(src, 'main.js'), 'utf8')

assert(!sojson.includes("require('vm')"), 'sojson plugin must not execute target code with node:vm')
assert(core.includes('traverse(current, visitor, undefined, {})'), 'each visitor needs a fresh state object')
assert(core.includes('function parseStrict'), 'strict generated-code parsing is required')
assert(core.includes('current = parseStrict(code)'), 'every visitor pass must generate and strictly reparse')
assert(main.includes('parseStrict(result)'), 'main must strictly reparse generated output')
assert(main.includes("getArg('--reference'"), 'main must support canonical fixture comparison')
assert(main.includes("getArg('--steps'"), 'main must support per-pass artifacts')

console.log(`AST static contracts: ok (${files.length} source files)`)
