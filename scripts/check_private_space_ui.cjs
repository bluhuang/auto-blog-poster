/* Run with NODE_PATH pointing to an installed Playwright Node package. */
const {chromium} = require('playwright');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');

(async () => {
  const secret = 'fixture password, not a site credential';
  const noteId = 'a'.repeat(64);
  const assetId = 'b'.repeat(64);
  const payload = {folders:[{name:'Hidden fixture folder', notes:[{
    id:noteId, title:'Confidential fixture note',
    html:`<p>PRIVATE_FIXTURE_TEXT</p><p>$$x^2$$</p><img src="private-asset:${assetId}" alt="Private image"><script>window.privateXss=true</script><img src="https://tracker.invalid/a" onerror="window.privateXss=true"><iframe src="https://tracker.invalid"></iframe><a href="javascript:alert(1)">Unsafe link</a>`,
  }]},{name:'coding/algorithms',notes:[{id:'c'.repeat(64),title:'Nested algorithm note',html:'<p>Nested content</p>'}]},{name:'coding/standard',notes:[{id:'d'.repeat(64),title:'Nested standard note',html:'<p>Standard content</p>'}]}],assets:{[assetId]:{mime:'image/png',data:'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a2ioAAAAASUVORK5CYII='}}};
  const salt = crypto.randomBytes(16), iv = crypto.randomBytes(12);
  const key = crypto.pbkdf2Sync(secret, salt, 600000, 32, 'sha256');
  const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);
  const ciphertext = Buffer.concat([cipher.update(JSON.stringify(payload)), cipher.final(), cipher.getAuthTag()]);
  const bundle = {version:1,kdf:'PBKDF2-SHA256',iterations:600000,salt:salt.toString('base64'),iv:iv.toString('base64'),ciphertext:ciphertext.toString('base64')};
  const shell = `<!doctype html><html><body><section data-private-space data-bundle-url="/bundle.json"><button data-private-lock hidden>Lock</button><div data-private-gate><form data-private-form><input type="password" required><button data-private-submit disabled>Unlock</button></form><p data-private-status>Preparing</p></div><div data-private-workspace hidden><nav data-private-tree></nav><h2 data-private-note-title tabindex="-1">Select a note</h2><div data-private-content></div></div></section><script src="/katex.min.js"></script><script src="/auto-render.min.js"></script><script src="/private-space.js"></script></body></html>`;
  const katexDist = path.join(__dirname, '../node_modules/katex/dist');
  const resources = {
    '/private-space.js':fs.readFileSync(path.join(__dirname,'../assets/js/private-space.js'),'utf8'),
    '/katex.min.js':fs.readFileSync(path.join(katexDist,'katex.min.js'),'utf8'),
    '/auto-render.min.js':fs.readFileSync(path.join(katexDist,'contrib/auto-render.min.js'),'utf8'),
  };
  const browser = await chromium.launch({headless:true,...(process.env.PRIVATE_TEST_BROWSER ? {executablePath:process.env.PRIVATE_TEST_BROWSER}: {})});
  try {
    for (const viewport of [{width:1440,height:1000},{width:390,height:844}]) {
      const context = await browser.newContext({viewport});
      await context.addInitScript(()=>{Storage.prototype.setItem=()=>{throw Error('No storage writes allowed')};});
      const requests = [];
      await context.route('**/*', async route=>{
        const url = new URL(route.request().url());
        requests.push(url.origin);
        if(url.origin !== 'https://private.test')throw Error('External private request '+url);
        if(url.pathname === '/bundle.json')return route.fulfill({contentType:'application/json',body:JSON.stringify(bundle)});
        if(resources[url.pathname])return route.fulfill({contentType:'text/javascript',body:resources[url.pathname]});
        return route.fulfill({contentType:'text/html',body:shell});
      });
      const page = await context.newPage();
      await page.goto('https://private.test/');
      await page.locator('[data-private-ready="true"]').waitFor();
      assert.equal(await page.locator('[data-private-tree]').innerText(),'');
      assert.equal(await page.locator('[data-private-workspace]').isVisible(),false);
      assert.ok(!(await page.content()).includes('Confidential fixture note'));
      await page.locator('input').fill('wrong password');
      await page.locator('[data-private-submit]').click();
      await page.locator('[data-private-status].is-error').waitFor();
      assert.equal(await page.locator('[data-private-tree]').innerText(),'');
      await page.locator('input').fill(secret);
      await page.locator('[data-private-submit]').click();
      await page.locator('[data-private-workspace]').waitFor({state:'visible'});
      assert.deepEqual(await page.locator('[data-private-tree] > details > summary').allTextContents(), ['Hidden fixture folder','coding']);
      const codingFolder = page.locator('[data-private-tree] > details').filter({has:page.locator(':scope > summary', {hasText:/^coding$/})});
      assert.deepEqual(await codingFolder.locator(':scope > div > details > summary').allTextContents(), ['algorithms','standard']);
      await page.locator('summary').first().click();
      await page.getByRole('button',{name:'Confidential fixture note'}).click();
      assert.ok((await page.locator('[data-private-content]').innerText()).includes('PRIVATE_FIXTURE_TEXT'));
      assert.equal(await page.locator('[data-private-content] .katex').count(),1);
      assert.equal(await page.locator('[data-private-content] script, [data-private-content] iframe, [data-private-content] [onerror]').count(),0);
      assert.equal(await page.evaluate(()=>window.privateXss),undefined);
      assert.ok((await page.locator('[data-private-content] img').first().getAttribute('src')).startsWith('blob:'));
      await page.locator('[data-private-lock]').click();
      assert.equal(await page.locator('[data-private-tree]').innerText(),'');
      assert.equal(await page.locator('[data-private-content]').innerText(),'');
      assert.equal(await page.locator('input').inputValue(),'');
      assert.equal(await page.locator('[data-private-workspace]').isVisible(),false);
      await page.reload();
      assert.equal(await page.locator('[data-private-workspace]').isVisible(),false);
      assert.ok(requests.every(origin=>origin === 'https://private.test'));
      console.log(`PASS private UI ${viewport.width}px: locked metadata, wrong password, correct password, math, encrypted image, XSS defense, lock/reload and no storage`);
      await context.close();
    }
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
