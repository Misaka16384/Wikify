// Run the real `markMatch` and `escapeHtml` out of app.js and print what they
// produce. Lifted by name rather than reimplemented: a copy of the function
// would keep passing after the shipped one changed.
const fs = require("fs");
const vm = require("vm");

const source = fs.readFileSync(process.argv[2], "utf8");

function lift(name) {
  const start = source.indexOf(`function ${name}(`);
  if (start === -1) throw new Error(`${name} is not in app.js any more`);
  // Walk braces from the first one after the signature.
  let i = source.indexOf("{", start);
  let depth = 0;
  for (; i < source.length; i++) {
    if (source[i] === "{") depth++;
    else if (source[i] === "}" && --depth === 0) return source.slice(start, i + 1);
  }
  throw new Error(`${name} has no closing brace`);
}

const sandbox = {};
vm.runInNewContext(`${lift("escapeHtml")}\n${lift("markMatch")}\nthis.markMatch = markMatch;`,
                   sandbox, { timeout: 5000 });

const cases = JSON.parse(process.argv[3]);
console.log(JSON.stringify(cases.map(([text, q]) => sandbox.markMatch(text, q))));
