// Run against a local Vite server. All API responses are synthetic and intercepted.
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const baseURL = process.env.FRONTEND_URL || 'http://127.0.0.1:5174';
const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined });
const context = await browser.newContext({locale:'it-IT',viewport:{width:1440,height:1000}});
let authenticated = false, currency = 'EUR', delayCategories = 0;
const user = {id:1,username:'alex',display_name:'Casa',is_admin:true,is_active:true};
const group = {id:1,name:'Gruppo amici',description:'Cena e viaggi',archived:false,created_by_user_id:1};
const supported = ['EUR','USD','CHF','GBP'];
const calls = [], errors = [];
await context.route(url => url.pathname.startsWith('/api/'), async route => {
  const request = route.request(), path = new URL(request.url()).pathname.replace('/api',''), language=request.headers()['accept-language'];
  calls.push({path,method:request.method(),language});
  let status=200, body={};
  const session=()=>({user,csrf_token:'fixture',timezone:'Europe/Rome',default_currency:currency,supported_currencies:supported});
  if(path==='/setup/status') body={setup_required:false};
  else if(path==='/auth/me') {body=authenticated?session():{detail:'Sign in required'};status=authenticated?200:401;}
  else if(path==='/auth/login') {authenticated=true;body=session();}
  else if(path==='/auth/logout') {authenticated=false;}
  else if(path==='/ready') body={status:'ready'};
  else if(path==='/meta') body={server_version:'fixture',default_currency:currency,supported_currencies:supported};
  else if(path==='/admin/settings') {if(request.method()==='PATCH')currency=request.postDataJSON().default_currency;body={default_currency:currency,supported_currencies:supported};}
  else if(path==='/users') body=[user];
  else if(path==='/groups') body=[group];
  else if(path==='/groups/1/members') body=[{id:1,user_id:1,display_name:'Casa',username:'alex',active:true}];
  else if(path==='/categories') body=[{id:1,name:'Spesa alimentare',display_name:language==='it'?'Spesa alimentare':'Groceries',slug:'groceries',icon_key:'shopping-basket'},{id:2,name:'Vacanze italiane',display_name:'Vacanze italiane',slug:null,icon_key:'tag'}];
  else if(path==='/dashboard') body={user,balances:[],debts:[],upcoming:[],recent_expenses:[],groups:[group]};
  else if(path==='/dashboard/statistics') body={month:'2026-11',current_month:'2026-11',available_months:['2026-11'],currencies:['EUR'],currency:'EUR',period:{start:'2026-11-01',end:'2026-11-01',days:1,is_current:true},comparison:{month:'2026-10',start:'2026-10-01',end:'2026-10-01',total_cents:0,change_cents:0,change_percent:null},summary:{total_cents:0,expense_count:0,average_cents:0,daily_average_cents:0,native_total_cents:0,legacy_total_cents:0},coverage:{legacy_included_count:0,legacy_excluded_count:0,legacy_transfers_excluded_count:0,legacy_missing_cost_count:0,legacy_nonpositive_count:0},categories:[],groups:[],trend:[],daily:[]};
  else if(path==='/auth/mfa/status')body={enabled:false,required:false,recovery_codes_remaining:0};
  else if(path==='/expenses/42')body={id:42,group_id:1,description:'Spesa originale',amount_cents:1234,currency:'CHF',paid_by_user_id:1,expense_date:'2026-10-31',notes:'Note originali',source:'NATIVE',splits:[{user_id:1,amount_cents:1234}]};
  else if(path==='/subscriptions/42')body={id:42,group_id:1,name:'Abbonamento originale',description:'Descrizione originale',amount_cents:1234,currency:'CHF',paid_by_user_id:1,start_date:'2026-10-31',recurrence_rule:'FREQ=MONTHLY;INTERVAL=1',splits:[{user_id:1,amount_cents:1234}]};
  else if(path.endsWith('/balances')||path.endsWith('/credits')||path==='/expenses'||path==='/subscriptions')body=[];
  if(path==='/categories' && delayCategories) await new Promise(resolve => setTimeout(resolve, delayCategories));
  await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
});
const page=await context.newPage();
page.setDefaultTimeout(10000);
page.on('pageerror',error=>errors.push(error.message));
const output=process.env.SCREENSHOT_DIR || '/tmp/splitcompanion-localization';
await fs.mkdir(output,{recursive:true});
try {
  await page.goto(baseURL);
  await page.getByRole('heading',{name:'Welcome back.'}).waitFor();
  assert.equal(await page.locator('html').getAttribute('lang'),'en');
  assert.equal(await page.getByLabel('Language',{exact:true}).inputValue(),'en');
  await page.screenshot({path:output+'/login-en-desktop.png',fullPage:true});
  await page.getByLabel('Language',{exact:true}).selectOption('it');
  await page.getByRole('heading',{name:'Ciao, di nuovo.'}).waitFor();
  await page.reload();
  await page.getByRole('heading',{name:'Ciao, di nuovo.'}).waitFor();
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:output+'/login-it-mobile.png',fullPage:true});
  await page.getByLabel('Lingua',{exact:true}).selectOption('en');
  await page.getByLabel('Username',{exact:true}).fill('alex');
  await page.getByLabel('Password',{exact:true}).fill('synthetic-password');
  await page.getByRole('button',{name:'Sign in to Split'}).click();
  await page.getByRole('link',{name:'Settings',exact:true}).click();
  await page.getByRole('heading',{name:'Settings',exact:true}).waitFor();
  await page.getByLabel('Default currency',{exact:true}).selectOption('USD');
  await page.getByRole('button',{name:'Save',exact:true}).click();
  await page.getByText('Default currency updated.',{exact:true}).waitFor();
  await page.screenshot({path:output+'/settings-en-mobile.png',fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true,'Mobile settings overflow');
  await page.getByLabel('Language',{exact:true}).selectOption('it');
  await page.getByRole('heading',{name:'Impostazioni',exact:true}).waitFor();
  await page.setViewportSize({width:1440,height:1000});
  await page.screenshot({path:output+'/settings-it-desktop.png',fullPage:true});
  delayCategories = 1800;
  await page.goto(baseURL+'/expenses/new');
  await page.getByRole('heading',{name:'Nuova spesa',exact:true}).waitFor();
  assert.equal(await page.getByLabel('Valuta',{exact:true}).inputValue(),'USD');
  await page.getByLabel('Quanto avete speso?',{exact:true}).fill('12,34');
  await page.getByLabel('Descrizione',{exact:true}).fill('Cena amici');
  const other=await context.newPage();
  await other.goto(baseURL+'/profile');
  await other.getByLabel('Lingua',{exact:true}).selectOption('en');
  await page.getByRole('heading',{name:'New expense',exact:true}).waitFor();
  assert.equal(await page.getByLabel('Currency',{exact:true}).inputValue(),'USD');
  assert.equal(await page.getByLabel('Description',{exact:true}).inputValue(),'Cena amici');
  assert.equal(await page.getByLabel('How much did you spend?',{exact:true}).inputValue(),'12,34');
  await page.getByRole('option',{name:'Groceries',exact:true}).waitFor({state:'attached'});
  delayCategories = 0;
  assert.equal(await page.getByRole('option',{name:'Vacanze italiane',exact:true}).count(),1);
  await page.screenshot({path:output+'/expense-en-desktop.png',fullPage:true});
  await page.goto(baseURL+'/subscriptions/new');
  await page.getByRole('heading',{name:'New subscription',exact:true}).waitFor();
  assert.equal(await page.getByLabel('Currency',{exact:true}).inputValue(),'USD');
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:output+'/subscription-en-mobile.png',fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true,'Mobile subscription form overflow');
  for(const resource of ['expenses','subscriptions']) {
    await page.goto(baseURL+'/'+resource+'/42/edit');
    await page.getByLabel('Currency',{exact:true}).waitFor();
    assert.equal(await page.getByLabel('Currency',{exact:true}).inputValue(),'CHF');
    await other.getByLabel('Language',{exact:true}).selectOption('it');
    await page.getByLabel('Valuta',{exact:true}).waitFor();
    assert.equal(await page.getByLabel('Valuta',{exact:true}).inputValue(),'CHF');
    await page.screenshot({path:output+'/'+resource+'-it-mobile.png',fullPage:true});
    await other.getByLabel('Lingua',{exact:true}).selectOption('en');
    await page.getByLabel('Currency',{exact:true}).waitFor();
  }
  assert.equal(errors.length,0,JSON.stringify(errors));
  assert.ok(calls.every(call=>['en','it'].includes(call.language)),'API language headers missing');
  console.log('PASS: English default, Italian persistence, live cross-tab language changes, preserved form drafts and custom names, admin USD default, existing CHF preservation, desktop/mobile rendering. Screenshots: '+output);
} catch (error) { console.error('PAGE ERRORS',errors); console.error('PAGE TEXT', await page.locator('body').innerText()); await page.screenshot({path:output+'/failure.png',fullPage:true}); throw error; } finally { await browser.close(); }
