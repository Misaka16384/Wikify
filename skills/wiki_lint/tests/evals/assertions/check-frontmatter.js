const fs = require('fs');
const path = require('path');

const RAW_REQUIRED = ['title', 'source', 'type', 'ingested', 'tags', 'summary'];
const WIKI_REQUIRED = ['title', 'category', 'sources', 'created', 'updated', 'tags', 'confidence', 'summary'];
const VALID_TYPES = ['articles', 'papers', 'repos', 'notes', 'data'];
const VALID_CATEGORIES = ['concept', 'topic', 'reference'];
const VALID_CONFIDENCE = ['high', 'medium', 'low'];

function parseFrontmatter(content) {
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return null;
  const fm = {};
  for (const line of match[1].split('\n')) {
    const m = line.match(/^(\w+):\s*(.+)/);
    if (m) fm[m[1]] = m[2];
  }
  return fm;
}

function checkFiles(dir, required, enumChecks) {
  const errors = [];
  if (!fs.existsSync(dir)) return errors;

  const files = fs.readdirSync(dir, { recursive: true })
    .filter(f => f.endsWith('.md') && !f.includes('_index.md'));

  for (const file of files) {
    const filePath = path.join(dir, file);
    if (!fs.statSync(filePath).isFile()) continue;
    const content = fs.readFileSync(filePath, 'utf-8');
    const fm = parseFrontmatter(content);
    if (!fm) {
      errors.push(`${file}: no frontmatter`);
      continue;
    }
    for (const field of required) {
      if (!fm[field]) errors.push(`${file}: missing ${field}`);
    }
    for (const [field, valid] of Object.entries(enumChecks)) {
      if (fm[field] && !valid.includes(fm[field])) {
        errors.push(`${file}: invalid ${field} '${fm[field]}'`);
      }
    }
  }
  return errors;
}

module.exports = async (output, context) => {
  const workspace = context.vars.workspace || './tests/workspace';
  const errors = [
    ...checkFiles(path.join(workspace, 'raw'), RAW_REQUIRED, { type: VALID_TYPES }),
    ...checkFiles(path.join(workspace, 'wiki'), WIKI_REQUIRED, {
      category: VALID_CATEGORIES,
      confidence: VALID_CONFIDENCE,
    }),
  ];

  if (errors.length > 0) {
    return { pass: false, reason: errors.slice(0, 10).join('; ') };
  }
  return { pass: true, score: 1.0, reason: 'All frontmatter valid' };
};
