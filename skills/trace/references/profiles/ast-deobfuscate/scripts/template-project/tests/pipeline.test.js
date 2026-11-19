const assert = require('assert')
const fs = require('fs')
const os = require('os')
const path = require('path')
const { spawnSync } = require('child_process')
const vm = require('vm')

const { detectFamily, generateCode, parseCode, parseStrict } = require('../src/lib/core')
const runAwsc = require('../src/plugins/awsc')
const runCommon = require('../src/plugins/common')
const runObfuscator = require('../src/plugins/obfuscator')
const runSojson = require('../src/plugins/sojson')


const obfuscatorInput = `
var ops = {
  "add": function (a, b) { return a + b; },
  "value": "ok"
};
var order = "0|1".split("|");
var index = 0;
while (true) {
  switch (order[index++]) {
    case "0": var total = ops["add"](1, 2); continue;
    case "1": var label = ops["value"]; continue;
  }
  break;
}
`

assert.equal(detectFamily(obfuscatorInput), 'obfuscator')
const transformed = generateCode(runObfuscator(parseCode(obfuscatorInput)))
parseStrict(transformed)
assert(!transformed.includes('ops["add"]'), 'dispatcher call should be inlined')
assert(!transformed.includes('ops["value"]'), 'dispatcher literal should be inlined')

const sojsonInput = `
var _0xabc = function () {
  return this.constructor.constructor("return process")().version;
};
var value = _0xabc();
`
const sojsonOutput = generateCode(runSojson(parseCode(sojsonInput)))
parseStrict(sojsonOutput)
assert(sojsonOutput.includes('return process'), 'unsafe bootstrap must remain unexecuted')
assert.throws(() => parseStrict('var = ;'))

function executeTrustedFixture(code) {
  const context = { result: null }
  context.globalThis = context
  vm.runInNewContext(code, context, { timeout: 1000 })
  return JSON.parse(JSON.stringify(context.result))
}

const voidInput = `
let calls = 0;
function sideEffect() { calls += 1; return 9; }
let value = void sideEffect();
globalThis.result = { calls, isUndefined: value === undefined };
`
const voidOutput = generateCode(runAwsc(parseCode(voidInput)))
parseStrict(voidOutput)
assert.deepEqual(executeTrustedFixture(voidOutput), { calls: 1, isUndefined: true })

const unusedSideEffectInput = `
let calls = 0;
function sideEffect() { calls += 1; }
var unused = sideEffect();
globalThis.result = calls;
`
const unusedSideEffectOutput = generateCode(runCommon(parseCode(unusedSideEffectInput)))
parseStrict(unusedSideEffectOutput)
assert.equal(executeTrustedFixture(unusedSideEffectOutput), 1)
assert(unusedSideEffectOutput.includes('sideEffect()'), 'unused impure initializer must be preserved')

const dispatcherSideEffectInput = `
var ops = { "f": function (a, b) { return a + a; } };
var indexValue = 0;
var effects = 0;
function sideEffect() { effects += 1; return 99; }
var answer = ops["f"](indexValue++, sideEffect());
globalThis.result = [answer, indexValue, effects];
`
const dispatcherSideEffectOutput = generateCode(runObfuscator(parseCode(dispatcherSideEffectInput)))
parseStrict(dispatcherSideEffectOutput)
assert.deepEqual(executeTrustedFixture(dispatcherSideEffectOutput), [0, 1, 1])
assert(dispatcherSideEffectOutput.includes('ops.f'), 'effectful dispatcher arguments must keep the original call')

const externalBindingInput = `
var order = ["0"];
var cursor = 0;
while (true) {
  switch (order[cursor++]) {
    case "0": work(); continue;
  }
  break;
}
consume(order);
`
const externalBindingOutput = generateCode(runObfuscator(parseCode(externalBindingInput)))
parseStrict(externalBindingOutput)
assert(externalBindingOutput.includes('var order'), 'externally referenced order binding must remain declared')
assert(externalBindingOutput.includes('while (true)'), 'loop with external binding references must not be unpacked')

const blockScopeInput = `
if (true) { let hidden = 1; globalThis.inside = hidden; }
globalThis.result = [globalThis.inside, typeof hidden];
`
const blockScopeOutput = generateCode(runCommon(parseCode(blockScopeInput)))
parseStrict(blockScopeOutput)
assert.deepEqual(executeTrustedFixture(blockScopeOutput), [1, 'undefined'])
assert(blockScopeOutput.includes('{\n  let hidden'), 'constant-if folding must preserve lexical block scope')

const propertyNameInput = `
var ops = { "read": function (a) { return target.a; } };
var target = { a: 7 };
globalThis.result = ops["read"](1);
`
const propertyNameOutput = generateCode(runObfuscator(parseCode(propertyNameInput)))
parseStrict(propertyNameOutput)
assert.equal(executeTrustedFixture(propertyNameOutput), 7)
assert(propertyNameOutput.includes('target.a'), 'non-computed member property names must not be substituted')

const mutatedTableInput = `
var table = { "value": "old" };
table["value"] = "new";
globalThis.result = table["value"];
`
const mutatedTableOutput = generateCode(runObfuscator(parseCode(mutatedTableInput)))
parseStrict(mutatedTableOutput)
assert.equal(executeTrustedFixture(mutatedTableOutput), 'new')

const computedKeyInput = `
var key = "value";
var table = { [key]: "kept" };
globalThis.result = table["value"];
`
const computedKeyOutput = generateCode(runObfuscator(parseCode(computedKeyInput)))
parseStrict(computedKeyOutput)
assert.equal(executeTrustedFixture(computedKeyOutput), 'kept')
assert(computedKeyOutput.includes('[key]'), 'dynamic computed table keys must not be treated as static names')

const breakCaseInput = `
var order = ["0"];
var cursor = 0;
while (true) {
  switch (order[cursor++]) {
    case "0": work(); break;
  }
  break;
}
`
const breakCaseOutput = generateCode(runObfuscator(parseCode(breakCaseInput)))
parseStrict(breakCaseOutput)
assert(breakCaseOutput.includes('while (true)'), 'switch break semantics must not be rewritten as continue semantics')

const repeatedLexicalInput = `
var order = ["0", "0"];
var cursor = 0;
globalThis.count = 0;
while (true) {
  switch (order[cursor++]) {
    case "0": let local = 1; globalThis.count += local; continue;
  }
  break;
}
globalThis.result = globalThis.count;
`
const repeatedLexicalOutput = generateCode(runObfuscator(parseCode(repeatedLexicalInput)))
parseStrict(repeatedLexicalOutput)
assert.equal(executeTrustedFixture(repeatedLexicalOutput), 2)
assert(!repeatedLexicalOutput.includes('while (true)'), 'safe array-driven loop should be unpacked')

const splitSideEffectInput = `
let splitCalls = 0;
String.prototype.split = function () { splitCalls += 1; return ["1", "0"]; };
var order = "0|1".split("|");
var cursor = 0;
globalThis.sequence = [];
while (true) {
  switch (order[cursor++]) {
    case "0": globalThis.sequence.push("0"); continue;
    case "1": globalThis.sequence.push("1"); continue;
  }
  break;
}
globalThis.result = [splitCalls, globalThis.sequence.join("")];
`
const splitSideEffectOutput = generateCode(runObfuscator(parseCode(splitSideEffectInput)))
parseStrict(splitSideEffectOutput)
assert.deepEqual(executeTrustedFixture(splitSideEffectOutput), [1, '10'])
assert(splitSideEffectOutput.includes('while (true)'), 'String.prototype.split dispatch must remain dynamic')

const nonZeroCursorInput = `
var order = ["a", "b"];
var cursor = 1;
globalThis.result = [];
while (true) {
  switch (order[cursor++]) {
    case "a": globalThis.result.push("a"); continue;
    case "b": globalThis.result.push("b"); continue;
  }
  break;
}
`
const nonZeroCursorOutput = generateCode(runObfuscator(parseCode(nonZeroCursorInput)))
parseStrict(nonZeroCursorOutput)
assert.deepEqual(executeTrustedFixture(nonZeroCursorOutput), ['b'])
assert(nonZeroCursorOutput.includes('while (true)'), 'non-zero cursor initialization must block unpacking')

const reassignedOrderInput = `
var order = ["a"];
order = ["b"];
var cursor = 0;
globalThis.result = [];
while (true) {
  switch (order[cursor++]) {
    case "a": globalThis.result.push("a"); continue;
    case "b": globalThis.result.push("b"); continue;
  }
  break;
}
`
const reassignedOrderOutput = generateCode(runObfuscator(parseCode(reassignedOrderInput)))
parseStrict(reassignedOrderOutput)
assert.deepEqual(executeTrustedFixture(reassignedOrderOutput), ['b'])
assert(reassignedOrderOutput.includes('while (true)'), 'reassigned order binding must block unpacking')

const shadowedTableInput = `
var ops = { "value": "outer" };
function read() {
  var ops = { "value": "inner" };
  return ops["value"];
}
globalThis.result = [ops["value"], read()];
`
const shadowedTableOutput = generateCode(runObfuscator(parseCode(shadowedTableInput)))
parseStrict(shadowedTableOutput)
assert.deepEqual(executeTrustedFixture(shadowedTableOutput), ['outer', 'inner'])

const closureBindingInput = `
var secret = "outer";
var ops = { "read": function () { return secret; } };
function read() { var secret = "inner"; return ops["read"](); }
globalThis.result = read();
`
const closureBindingOutput = generateCode(runObfuscator(parseCode(closureBindingInput)))
parseStrict(closureBindingOutput)
assert.equal(executeTrustedFixture(closureBindingOutput), 'outer')
assert(closureBindingOutput.includes('ops.read()'), 'dispatcher wrappers with free bindings must remain calls')

const hoistedVarInput = `
if (false) var hoisted = 1;
globalThis.result = typeof hoisted;
`
const hoistedVarOutput = generateCode(runCommon(parseCode(hoistedVarInput)))
parseStrict(hoistedVarOutput)
assert.equal(executeTrustedFixture(hoistedVarOutput), 'undefined')
assert(hoistedVarOutput.includes('if (false)'), 'constant-if must preserve var hoisting semantics')

const directiveInput = `
("use strict");
globalThis.result = (function () { return this === globalThis; })();
`
const directiveOutput = generateCode(runCommon(parseCode(directiveInput)))
parseStrict(directiveOutput)
assert.equal(executeTrustedFixture(directiveOutput), true)

const mutableIntrinsicInput = `
let calls = 0;
Array.prototype.toString = function () { calls += 1; return "x"; };
globalThis.result = [[] + [], calls];
`
const mutableIntrinsicOutput = generateCode(runCommon(parseCode(mutableIntrinsicInput)))
parseStrict(mutableIntrinsicOutput)
assert.deepEqual(executeTrustedFixture(mutableIntrinsicOutput), ['xx', 2])
assert(mutableIntrinsicOutput.includes('[] + []'), 'binary folding must not assume mutable object coercion intrinsics')

const defaultCaseInput = `
function runDefault() {
  var order = ["missing"];
  var cursor = 0;
  while (true) {
    switch (order[cursor++]) {
      case "known": return 0;
      default: return 9;
    }
    break;
  }
  return -1;
}
globalThis.result = runDefault();
`
const defaultCaseOutput = generateCode(runObfuscator(parseCode(defaultCaseInput)))
parseStrict(defaultCaseOutput)
assert.equal(executeTrustedFixture(defaultCaseOutput), 9)
assert(defaultCaseOutput.includes('default:'), 'default cases must block static unpacking')

const dynamicCaseInput = `
var effects = 0;
function label() { effects += 1; return "0"; }
function runDynamic() {
  var order = ["0"];
  var cursor = 0;
  while (true) {
    switch (order[cursor++]) {
      case label(): return effects;
    }
    break;
  }
  return -1;
}
globalThis.result = [runDynamic(), effects];
`
const dynamicCaseOutput = generateCode(runObfuscator(parseCode(dynamicCaseInput)))
parseStrict(dynamicCaseOutput)
assert.deepEqual(executeTrustedFixture(dynamicCaseOutput), [1, 1])
assert(dynamicCaseOutput.includes('case label()'), 'dynamic case labels must block static unpacking')

const inheritedSetterInput = `
var setterCalls = 0;
Object.prototype.__traceSetter = 0;
Object.defineProperty(Object.prototype, "inherited", { set() { setterCalls += 1; }, configurable: true });
var object = {};
object.inherited = 1;
globalThis.result = [setterCalls, Object.prototype.hasOwnProperty.call(object, "inherited")];
delete Object.prototype.inherited;
`
const inheritedSetterOutput = generateCode(runObfuscator(parseCode(inheritedSetterInput)))
parseStrict(inheritedSetterOutput)
assert.deepEqual(executeTrustedFixture(inheritedSetterOutput), [1, false])

const topLevelBindingInput = `
var externallyVisible = 1;
globalThis.result = Object.prototype.hasOwnProperty.call(globalThis, "externallyVisible");
`
const topLevelBindingOutput = generateCode(runCommon(parseCode(topLevelBindingInput)))
parseStrict(topLevelBindingOutput)
assert.equal(executeTrustedFixture(topLevelBindingOutput), true)
assert(topLevelBindingOutput.includes('externallyVisible'), 'top-level bindings may be external API and must remain')

const directEvalSwitchInput = `
function inspectCursor() {
  var order = ["0"];
  var cursor = 0;
  while (true) {
    switch (order[cursor++]) {
      case "0": return eval("cursor");
    }
    break;
  }
  return -1;
}
globalThis.result = inspectCursor();
`
const directEvalSwitchOutput = generateCode(runObfuscator(parseCode(directEvalSwitchInput)))
parseStrict(directEvalSwitchOutput)
assert.equal(executeTrustedFixture(directEvalSwitchOutput), 1)
assert(directEvalSwitchOutput.includes('while (true)'), 'direct eval must block binding-sensitive unpacking')

const dispatcherBeforeInitInput = `
try { globalThis.result = ops["value"]; } catch (error) { globalThis.result = error.name; }
var ops = { "value": "late" };
`
const dispatcherBeforeInitOutput = generateCode(runObfuscator(parseCode(dispatcherBeforeInitInput)))
parseStrict(dispatcherBeforeInitOutput)
assert.equal(executeTrustedFixture(dispatcherBeforeInitOutput), 'TypeError')

const dispatcherEvalMutationInput = `
var ops = { "value": 1 };
eval("ops.value = 2");
globalThis.result = ops["value"];
`
const dispatcherEvalMutationOutput = generateCode(runObfuscator(parseCode(dispatcherEvalMutationInput)))
parseStrict(dispatcherEvalMutationOutput)
assert.equal(executeTrustedFixture(dispatcherEvalMutationOutput), 2)

const lateSwitchBindingsInput = `
globalThis.result = [];
try {
  while (true) {
    switch (order[cursor++]) {
      case "0": globalThis.result.push("ran"); continue;
    }
    break;
  }
} catch (error) { globalThis.result.push(error.name); }
var order = ["0"];
var cursor = 0;
`
const lateSwitchBindingsOutput = generateCode(runObfuscator(parseCode(lateSwitchBindingsInput)))
parseStrict(lateSwitchBindingsOutput)
assert.deepEqual(executeTrustedFixture(lateSwitchBindingsOutput), ['TypeError'])

const sequenceDirectiveInput = `
"use strict", 0;
globalThis.result = (function () { return this === globalThis; })();
`
const sequenceDirectiveOutput = generateCode(runCommon(parseCode(sequenceDirectiveInput)))
parseStrict(sequenceDirectiveOutput)
assert.equal(executeTrustedFixture(sequenceDirectiveOutput), true)

const earlyBreakInput = `
var order = ["0"];
var cursor = 0;
globalThis.result = [];
while (true) {
  switch (order[cursor++]) {
    case "0": if (true) break; globalThis.result.push("bad"); continue;
  }
  break;
}
`
const earlyBreakOutput = generateCode(runObfuscator(parseCode(earlyBreakInput)))
parseStrict(earlyBreakOutput)
assert.deepEqual(executeTrustedFixture(earlyBreakOutput), [])
assert(earlyBreakOutput.includes('while (true)'), 'early switch control must block unpacking')

const mergeOrderingInput = `
var events = [];
var object = {};
events.push("between");
object["value"] = 1;
globalThis.result = [events[0], object.value];
`
const mergeOrderingOutput = generateCode(runObfuscator(parseCode(mergeOrderingInput)))
parseStrict(mergeOrderingOutput)
assert.deepEqual(executeTrustedFixture(mergeOrderingOutput), ['between', 1])
assert(mergeOrderingOutput.indexOf('events.push') < mergeOrderingOutput.indexOf('object.value = 1'))

const throwingAssignmentInput = `
var object = {};
function fail() { throw new Error("expected"); }
try { object.value = fail(); } catch (_) {}
globalThis.result = typeof object;
`
const throwingAssignmentOutput = generateCode(runObfuscator(parseCode(throwingAssignmentInput)))
parseStrict(throwingAssignmentOutput)
assert.equal(executeTrustedFixture(throwingAssignmentOutput), 'object')

const cliDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ast-profile-cli-'))
try {
  const inputFile = path.join(cliDir, 'input.js')
  const outputFile = path.join(cliDir, 'output.js')
  const stepsDir = path.join(cliDir, 'steps')
  const metricsFile = path.join(cliDir, 'metrics.json')
  fs.writeFileSync(inputFile, obfuscatorInput)

  const mainResult = spawnSync(
    process.execPath,
    [path.resolve(__dirname, '..', 'src', 'main.js'), '-i', inputFile, '-o', outputFile, '--steps', stepsDir],
    { encoding: 'utf8' },
  )
  assert.equal(mainResult.status, 0, mainResult.stderr || mainResult.stdout)
  const stepFiles = fs.readdirSync(stepsDir).filter((name) => name.endsWith('.js')).sort()
  assert(stepFiles.length >= 10, 'CLI must write one artifact per visitor pass')
  for (const file of stepFiles) parseStrict(fs.readFileSync(path.join(stepsDir, file), 'utf8'))
  parseStrict(fs.readFileSync(outputFile, 'utf8'))

  const metricsResult = spawnSync(
    process.execPath,
    [path.resolve(__dirname, '..', 'src', 'tools', 'collect-residue-metrics.js'), outputFile, metricsFile],
    { encoding: 'utf8' },
  )
  assert.equal(metricsResult.status, 0, metricsResult.stderr || metricsResult.stdout)
  assert.equal(typeof JSON.parse(fs.readFileSync(metricsFile, 'utf8')).loopSwitchCount, 'number')
} finally {
  fs.rmSync(cliDir, { recursive: true, force: true })
}

console.log('AST pipeline fixture: ok')
