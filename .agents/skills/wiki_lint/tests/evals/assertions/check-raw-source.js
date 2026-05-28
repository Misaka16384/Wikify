const fs = require('fs');
const path = require('path');

module.exports = async (output, context) => {
  const workspace = context.vars.workspace || './tests/workspace';
  const rawDir = path.join(workspace, 'raw', 'articles');

  if (!fs.existsSync(rawDir)) {
    return { pass: false, reason: 'raw/articles/ directory does not exist' };
  }

  const files = fs.readdirSync(rawDir).filter(f => f !== '_index.md' && f.endsWith('.md'));
  if (files.length === 0) {
    return { pass: false, reason: 'No raw source files created' };
  }

  const content = fs.readFileSync(path.join(rawDir, files[0]), 'utf-8');
  const requiredFields = ['title:', 'source:', 'type:', 'ingested:', 'tags:', 'summary:'];
  const missing = requiredFields.filter(f => !content.includes(f));

  if (missing.length > 0) {
    return { pass: false, reason: `Missing frontmatter fields: ${missing.join(', ')}` };
  }

  return {
    pass: true,
    score: 1.0,
    reason: `Created ${files.length} source(s) with valid frontmatter`,
  };
};
