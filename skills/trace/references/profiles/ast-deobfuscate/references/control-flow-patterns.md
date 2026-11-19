# Control-Flow Safety Patterns

The maintained implementations live only in `scripts/template-project/src/visitors/`. This reference defines proof gates; it does not carry a second visitor copy.

## Dispatcher Tables

`inline-dispatcher.js` may inline a table call/read only when:

1. The use resolves to the exact Babel binding that declared the table; name equality is insufficient.
2. The table is a static object expression with no dynamic key, spread, getter, setter, `__proto__`, alias, or property mutation.
3. The wrapper contains one simple return, all referenced identifiers are parameters, and it does not use `this`, `arguments`, assignment, update, meta properties, await/yield, or nested functions.
4. Arguments are primitive literals, exact in count, and cannot change evaluation order or multiplicity.
5. The member is a read, not an assignment/update/delete target.

Shadowed identifiers, effectful arguments, getters, missing/extra arguments, and unknown calls remain unchanged.

## While-Switch

`while-switch-unpack.js` intentionally accepts a narrow shape:

- literal `while (true)` or `while (!0)`
- body is exactly `switch (...)` followed by an unlabeled loop `break`
- discriminant is `order[cursor++]`
- `order` is an unmodified array literal of string/number literals
- `cursor` is initialized to numeric zero and has no mutation except that postfix increment
- both bindings are referenced only by the discriminant and nowhere else
- every case label is a static string/number; any default or dynamic label blocks the pass
- every selected case ends in unlabeled `continue`, `return`, or `throw`

Each emitted case chunk remains in its own block so repeated lexical declarations keep per-iteration scope.

String `.split('|')` tables are detected by residue metrics but are not unpacked by default because `String.prototype.split` can be replaced. A target-specific opt-in requires a fixture that proves the intrinsic and default/dynamic-case behavior.

## Constant Branches

`constant-if.js` only folds primitive literal tests. It preserves the original `if` whenever either branch contains a `var` or function declaration, because removing an unreachable branch can still remove a hoisted binding.

Blocks are preserved rather than spliced into the parent so `let`/`const` scope remains intact.

## Object Assignment Merging

Moving `object.key = value` into an object literal can change evaluation timing and `[[Set]]` versus property-definition semantics, including inherited setters. The bundled default pipeline therefore does not perform this transform.

## Required Regression Fixtures

Any new control-flow visitor needs positive and negative fixtures for:

- side effects and exception timing
- shadowed bindings
- `var` hoisting and lexical block scope
- default/dynamic switch labels
- nonzero/reassigned cursor/order
- repeated lexical declarations
- inherited setters/getters
- strict parse after each pass

When runtime state prevents proof, keep the structure and produce an instrumented version instead.

## Minimum Artifacts

1. `--steps` output for each visitor pass.
2. Final strict-parsed readable output.
3. Fixed fixture/reference result.
4. Residue metrics and a list of deliberately retained structures.
