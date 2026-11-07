// Dependency-free structural checks. Run before npm install or the TypeScript build.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const projectRoot = path.resolve(__dirname, '..');
const tsconfig = JSON.parse(fs.readFileSync(path.join(projectRoot, 'tsconfig.json'), 'utf8'));
const pkg = JSON.parse(fs.readFileSync(path.join(projectRoot, 'package.json'), 'utf8'));

test('TypeScript manifest lists existing, unique core source files', () => {
    assert.ok(Array.isArray(tsconfig.files) && tsconfig.files.length >= 37,
        'the imported core should list at least its original 37 TypeScript files');
    assert.equal(tsconfig.files[tsconfig.files.length - 1],
        './src/dragonBones/core/ModuleExports.ts',
        'module exports must run after the full DragonBones namespace is initialized');
    const sourceRoot = path.join(projectRoot, 'src', 'dragonBones') + path.sep;
    const seen = new Set();
    for (const name of tsconfig.files) {
        const fullPath = path.resolve(projectRoot, name);
        assert.ok(fullPath.startsWith(sourceRoot) && fullPath.endsWith('.ts'),
            `unexpected source path: ${name}`);
        assert.ok(!seen.has(fullPath), `duplicate source entry: ${name}`);
        seen.add(fullPath);
        assert.ok(fs.statSync(fullPath).isFile(), `missing TypeScript source: ${name}`);
    }
});

test('package entry points match the TypeScript build outputs', () => {
    const options = tsconfig.compilerOptions;
    assert.equal(options.target.toLowerCase(), 'es5');
    assert.equal(options.declaration, true);
    assert.equal(path.resolve(projectRoot, pkg.main), path.resolve(projectRoot, options.outFile));
    const declarationPath = options.outFile.replace(/\.js$/, '.d.ts');
    assert.equal(path.resolve(projectRoot, pkg.types), path.resolve(projectRoot, declarationPath));
    assert.ok(pkg.scripts['build:ts'].includes('tsc'));
    assert.ok(pkg.scripts.build.includes('npm run build:ts'));
    assert.ok(pkg.scripts.test.includes('node --test'));
});

test('the standalone package preserves its MIT license', () => {
    assert.equal(pkg.license, 'MIT');
    assert.ok(pkg.files.includes('LICENSE') && pkg.files.includes('out/'));
    const license = fs.readFileSync(path.join(projectRoot, 'LICENSE'), 'utf8');
    assert.match(license, /The MIT License \(MIT\)/);
    assert.match(license, /Copyright \(c\) 2012-2025/);
});

test('every Node regression test file has valid JavaScript syntax', () => {
    const testDirectory = path.join(projectRoot, 'tests');
    const filenames = fs.readdirSync(testDirectory)
        .filter(name => name.endsWith('.test.cjs'));
    assert.ok(filenames.length >= 7, 'expected regression test files');
    for (const name of filenames) {
        const result = spawnSync(process.execPath,
            ['--check', path.join(testDirectory, name)],
            { encoding: 'utf8' });
        assert.equal(result.status, 0, `${name}: ${result.stderr || result.error || ''}`);
    }
});

test('module adapter reuses the global declared by the core bundle', () => {
    const core = fs.readFileSync(
        path.join(projectRoot, 'src', 'dragonBones', 'core', 'DragonBones.ts'), 'utf8');
    const adapter = fs.readFileSync(
        path.join(projectRoot, 'src', 'dragonBones', 'core', 'ModuleExports.ts'), 'utf8');

    assert.match(core, /\bvar\s+global\b/,
        'the core must provide the global variable used by the module adapter');
    assert.doesNotMatch(adapter, /\bdeclare\s+(?:var|let|const)\s+global\b/,
        'a second global declaration may conflict with the core under TypeScript');
});

test('TypeScript manifest covers every core .ts source', () => {
    const root = path.join(projectRoot, 'src', 'dragonBones');
    const pending = [root];
    const discovered = [];
    while (pending.length > 0) {
        const directory = pending.pop();
        for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
            const fullPath = path.join(directory, entry.name);
            if (entry.isDirectory()) {
                pending.push(fullPath);
            }
            else if (entry.isFile() && entry.name.endsWith('.ts')) {
                discovered.push(fullPath);
            }
        }
    }
    const expected = tsconfig.files.map(name => path.resolve(projectRoot, name));
    assert.deepEqual(discovered.sort(), expected.sort(),
        'tsconfig.files must include every core TypeScript source');
});
