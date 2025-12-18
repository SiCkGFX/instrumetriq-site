import { promises as fs } from 'node:fs';
import path from 'node:path';

const ROOT = process.cwd();

const TARGET_DIRS = [
  path.join(ROOT, 'src', 'pages'),
  path.join(ROOT, 'src', 'components'),
];

const FORBIDDEN = [
  { label: 'multiple social media platforms', re: /multiple\s+social\s+media\s+platforms/i },
  { label: 'diverse social media', re: /diverse\s+social\s+media/i },
  { label: 'lexicon-based scoring', re: /lexicon[-\s]*based\s+scoring/i },
];

async function* walkFiles(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      yield* walkFiles(full);
      continue;
    }

    if (!entry.isFile()) continue;
    if (!full.endsWith('.astro')) continue;

    yield full;
  }
}

function toRepoRel(filePath) {
  return path.relative(ROOT, filePath).replaceAll('\\', '/');
}

function findAllMatches(text, re) {
  const out = [];
  const globalRe = new RegExp(re.source, re.flags.includes('g') ? re.flags : `${re.flags}g`);
  for (;;) {
    const m = globalRe.exec(text);
    if (!m) break;
    out.push({ index: m.index, match: m[0] });
    if (m.index === globalRe.lastIndex) globalRe.lastIndex++;
  }
  return out;
}

function lineForIndex(text, index) {
  // 1-based line number
  let line = 1;
  for (let i = 0; i < index && i < text.length; i++) {
    if (text.charCodeAt(i) === 10) line++;
  }
  return line;
}

async function main() {
  const violations = [];

  for (const dir of TARGET_DIRS) {
    try {
      for await (const file of walkFiles(dir)) {
        const content = await fs.readFile(file, 'utf8');
        for (const rule of FORBIDDEN) {
          for (const m of findAllMatches(content, rule.re)) {
            violations.push({
              file,
              line: lineForIndex(content, m.index),
              label: rule.label,
              snippet: m.match,
            });
          }
        }
      }
    } catch (err) {
      // If a directory doesn't exist (unlikely), treat as non-fatal.
      if (err && err.code === 'ENOENT') continue;
      throw err;
    }
  }

  if (violations.length) {
    for (const v of violations) {
      // Format: path:line: message
      console.error(`${toRepoRel(v.file)}:${v.line}: forbidden phrase (${v.label})`);
    }
    process.exit(1);
  }

  console.log('lint:wording passed');
}

await main();
