import { expect, it } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import { messages } from './src/i18n/index';
const root = fileURLToPath(new URL('./src/', import.meta.url));
const sourceFiles = (directory) => readdirSync(directory, {withFileTypes:true}).flatMap(entry => entry.isDirectory() ? (entry.name === 'i18n' ? [] : sourceFiles(join(directory,entry.name))) : /\.tsx?$/.test(entry.name) && !entry.name.includes('.test.') ? [join(directory,entry.name)] : []);
it('covers every literal translation key in both languages and leaves no unlocalized JSX prose', () => {
  const brands = new Set(['Split', 'Companion', 'Split Companion', 'split companion', 'Splitwise']);
  for (const file of sourceFiles(root)) {
    const source = ts.createSourceFile(file, readFileSync(file,'utf8'), ts.ScriptTarget.Latest, true);
    const visit = (node) => {
      if (ts.isCallExpression(node) && node.expression.getText(source) === 't' && node.arguments[0] && ts.isStringLiteral(node.arguments[0])) {
        const key = node.arguments[0].text;
        expect(messages.en[key], `${file}: ${key}`).toBeDefined();
        expect(messages.it[key], `${file}: ${key}`).toBeDefined();
      }
      if (ts.isJsxText(node) && /[a-zà-ÿ]/i.test(node.text)) {
        expect(brands.has(node.text.trim()), `${file}: raw JSX text ${node.text.trim()}`).toBe(true);
      }
      ts.forEachChild(node, visit);
    };
    visit(source);
  }
});
