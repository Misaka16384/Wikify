const fs = require('fs');
const path = require('path');

module.exports = async (output, context) => {
  const workspace = context.vars.workspace || './tests/workspace';
  const errors = [];

  const walkDirs = (dir) => {
    if (!fs.existsSync(dir)) return;
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    const subdirs = entries.filter(e => e.isDirectory() && !e.name.startsWith('.'));

    for (const sub of subdirs) {
      const subPath = path.join(dir, sub.name);
      const indexPath = path.join(subPath, '_index.md');
      if (!fs.existsSync(indexPath)) {
        errors.push(`Missing _index.md in ${path.relative(workspace, subPath)}`);
      }
      walkDirs(subPath);
    }
  };

  walkDirs(path.join(workspace, 'raw'));
  walkDirs(path.join(workspace, 'wiki'));

  if (errors.length > 0) {
    return { pass: false, reason: errors.join('; ') };
  }
  return { pass: true, score: 1.0, reason: 'All directories have _index.md' };
};
