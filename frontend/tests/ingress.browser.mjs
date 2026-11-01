// Run after `npm run build`: node --test tests/ingress.browser.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const dist = fileURLToPath(new URL('../dist/', import.meta.url));
const mount = '/api/hassio_ingress/test_token/';
const mime = { '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png', '.webmanifest': 'application/manifest+json' };

for (const ingress of [true, false]) for (const language of ['en', 'it']) {
  test(`${ingress ? 'Ingress iframe' : 'direct'}: ${language} deep routes, assets, account and forms`, async () => {
    let authenticated = false;
    const requests = [];
    const prefix = ingress ? mount : '/';
    const user = {id: 1, username: 'alex', display_name: 'Alex', is_admin: true, is_active: true, avatar_version: 'v1'};
    const session = {user, csrf_token: 'csrf-fixture', timezone: 'UTC', default_currency: 'USD'};
    const server = createServer(async (req, res) => {
      const path = new URL(req.url, 'http://localhost').pathname;
      requests.push({path, method: req.method, language: req.headers['accept-language'], csrf: req.headers['x-csrf-token']});
      if (path === '/frame') { res.setHeader('Content-Type', 'text/html'); res.end(`<link rel="icon" href="data:," /><iframe src="${mount}profile" width="1200" height="900"></iframe>`); return; }
      if (!path.startsWith(prefix)) { res.writeHead(404).end(); return; }
      const local = '/' + path.slice(prefix.length);
      if (local.startsWith('/api/')) {
        res.setHeader('Content-Type', 'application/json');
        const data = {'/api/setup/status': {setup_required: false}, '/api/ready': {status:'ready'}, '/api/meta': {server_version:'test',source_available:true}, '/api/users': [user], '/api/groups': [{id:1,name:'Home',archived:false}], '/api/categories': [], '/api/groups/1/members': [{id:1,user_id:1,display_name:'Alex',username:'alex',active:true}], '/api/auth/mfa/status': {enabled:false}, '/api/settings': {default_currency:'USD'}};
        if (local === '/api/auth/login') {authenticated=true; res.end(JSON.stringify(session)); return;}
        if (local === '/api/auth/logout') {authenticated=false; res.writeHead(204).end(); return;}
        if (local === '/api/auth/me') {res.statusCode=authenticated ? 200 : 401; res.end(JSON.stringify(authenticated ? session : {detail:'Unauthorized'})); return;}
        if (local in data) {res.end(JSON.stringify(data[local])); return;}
        res.writeHead(404).end('{"detail":"Fixture endpoint unavailable"}'); return;
      }
      try {
        const extension = /\.[^.]+$/.exec(local)?.[0];
        if (extension && mime[extension]) {res.setHeader('Content-Type', mime[extension]); res.end(await readFile(dist + local)); return;}
        let html = await readFile(dist + '/index.html', 'utf8');
        html = html.replace(/<base\b[^>]*>/, '');
        html = html.replace('<head>', `<head><base href="${prefix}" />${ingress ? '<meta name="split-ingress" content="true">' : ''}`);
        res.setHeader('Content-Type','text/html'); res.end(html);
      } catch { res.writeHead(404).end(); }
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const browser = await chromium.launch({headless:true, ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? {executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE} : process.platform === 'darwin' ? {channel:'chrome'} : {})});
    try {
      const context = await browser.newContext();
      await context.addInitScript(({language}) => localStorage.setItem('split-companion-language',language), {language});
      const page = await context.newPage();
      const errors=[]; page.on('pageerror',error=>errors.push(error.message));
      const origin = `http://127.0.0.1:${server.address().port}`;
      await page.goto(origin + (ingress ? '/frame' : '/profile'));
      const frame = ingress ? page.frames().find(frame=>frame.url().includes(mount)) : page.mainFrame();
      await frame.getByLabel('Username', {exact:true}).fill('alex', {timeout:8000});
      await frame.getByLabel('Password', {exact:true}).fill('fixture-password');
      await frame.locator('form button[type="submit"]').click();
      await frame.locator('nav').waitFor();
      assert.equal(new URL(frame.url()).pathname, prefix);
      await frame.locator(`nav a[href="${prefix}profile"]`).click();
      await frame.getByRole('heading', {name:language==='it'?'Impostazioni':'Settings',exact:true}).waitFor();
      assert.equal(await frame.locator('a.settings-row[href$="api/source"]').getAttribute('href'), prefix+'api/source');
      assert.equal(await frame.locator('.skip-link').evaluate(link => new URL(link.href).pathname), prefix+'profile');
      await frame.getByLabel(language==='it'?'Lingua':'Language', {exact:true}).selectOption(language==='it'?'en':'it');
      assert.equal(await frame.locator('html').getAttribute('lang'),language==='it'?'en':'it');
      await frame.getByLabel(language==='it'?'Language':'Lingua', {exact:true}).selectOption(language);
      if (ingress) {
        await frame.evaluate(()=>window.dispatchEvent(new Event('beforeinstallprompt')));
        assert.equal(await frame.locator('.install-banner').count(),0);
        assert.equal(await frame.getByRole('button',{name:language==='it'?'Attiva su questo dispositivo':'Enable on this device'}).count(),0);
      }
      await frame.goto(origin+prefix+'expenses/new');
      await frame.getByRole('heading',{name:language==='it'?'Nuova spesa':'New expense',exact:true}).waitFor();
      assert.equal(await frame.locator('input[value="USD"]').count(),1);
      await frame.goto(origin+prefix+'subscriptions/new');
      await frame.getByRole('heading',{name:language==='it'?'Nuovo abbonamento':'New subscription',exact:true}).waitFor();
      assert.equal(await frame.locator('input[value="USD"]').count(),1);
      await frame.goto(origin+prefix+'profile');
      await frame.getByRole('button',{name:language==='it'?'Esci':'Sign out',exact:true}).click();
      await frame.getByLabel('Username', {exact:true}).waitFor();
      assert.equal(new URL(frame.url()).pathname,prefix);
      const logout=requests.find(request=>request.path===prefix+'api/auth/logout');
      assert.equal(logout?.method,'POST'); assert.equal(logout?.csrf,'csrf-fixture'); assert.equal(logout?.language,language);
      assert.ok(requests.some(request=>request.path.startsWith(prefix+'assets/')));
      assert.ok(requests.some(request=>request.path===prefix+'api/users/1/avatar'));
      if (ingress) {
        assert.deepEqual(requests.filter(request=>request.path!=='/frame'&&!request.path.startsWith(prefix)),[]);
        assert.ok(!requests.some(request=>request.path.endsWith('/sw.js')));
      } else assert.ok(requests.some(request=>request.path==='/sw.js'));
      assert.deepEqual(errors,[]);
    } finally {await browser.close(); await new Promise(resolve=>server.close(resolve));}
  });
}
