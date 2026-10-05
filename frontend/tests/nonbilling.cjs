// Run in the isolated Playwright Docker image; all API traffic is mocked.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');

const root = process.env.WEB_URL || 'http://localhost:3000';
const evidence = process.env.SCREENSHOT_DIR || '/evidence/screenshots';
const cohort = (id, name) => ({ id, name, start_date: '2026-10-02', end_date: null, status: 'planned', consent_required: true, enrolled: false });
const memberships = [1, 2].map((id) => ({ institution_id: id, institution_name: `Institution ${id}`, role: 'institution_admin' }));

async function mock(page, handler = () => undefined) {
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    const response = await handler(path, route.request());
    if (response) return route.fulfill({ status: response.status || 200, json: response.body });
    if (path === '/web/csrf') return route.fulfill({ json: { csrf_token: 'isolated-csrf' } });
    if (path === '/web/me') return route.fulfill({ json: { user: { id: 1, email: 'admin@example.test' }, memberships } });
    if (path.includes('/billing/')) return route.fulfill({ json: { origin: 'free', subscription_status: null } });
    return route.fulfill({ json: [] });
  });
}

async function portal(page) {
  await page.goto(`${root}/portal`);
  await page.getByLabel('Institution', { exact: true }).selectOption('1');
  await page.getByRole('button', { name: 'Pilot cohorts' }).click();
}

(async () => {
  await fs.mkdir(evidence, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  let passed = 0;
  async function test(name, run) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on('pageerror', (error) => console.error('BROWSER', error.message));
    try { await run(page); passed++; console.log(`PASS ${name}`); }
    catch (error) { await page.screenshot({ path: `${evidence}/failure.png`, fullPage: true }); console.error(await page.locator('body').innerText()); throw error; }
    finally { await page.close(); }
  }
  try {
    await test('first cohort form opens, validates and submits from empty institution', async (page) => {
      const rows = [];
      await mock(page, (path, request) => {
        if (path === '/portal/1/cohorts') {
          if (request.method() === 'POST') {
            const input = request.postDataJSON();
            assert.equal(input.name, 'First pilot');
            assert.equal(request.headers()['x-csrftoken'], 'isolated-csrf');
            rows.push(cohort(11, input.name));
            return { body: { ...rows[0], selected_plan_ids: [], selected_activity_ids: [], enrolled_count: 0, report: null } };
          }
          return { body: rows };
        }
      });
      await portal(page);
      await page.getByText('No pilot cohorts yet', { exact: true }).waitFor();
      await page.getByRole('button', { name: 'New cohort' }).click();
      await page.getByRole('heading', { name: 'Create pilot cohort' }).waitFor();
      await page.getByLabel('Cohort name').fill('First pilot');
      await page.getByLabel('Start date').fill('2026-10-02');
      await page.screenshot({ path: `${evidence}/portal-desktop.png`, fullPage: true });
      await page.setViewportSize({ width: 390, height: 844 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'mobile page must not overflow');
      await page.screenshot({ path: `${evidence}/portal-mobile.png`, fullPage: true });
      await page.getByRole('button', { name: 'Create cohort', exact: true }).click();
      await page.getByRole('button', { name: /First pilot/ }).waitFor();
    });

    await test('backoffice login uses CSRF and denied account can sign out', async (page) => {
      let loggedIn = false;
      await mock(page, (path, request) => {
        if (path === '/web/backoffice/boundary') return { status: loggedIn ? 403 : 401, body: { detail: 'Access required' } };
        if (path === '/web/login') {
          assert.equal(request.headers()['x-csrftoken'], 'isolated-csrf');
          assert.equal(request.postDataJSON().email, 'staff@example.test');
          loggedIn = true; return { body: {} };
        }
        if (path === '/web/logout') { loggedIn = false; return { body: {} }; }
      });
      await page.goto(`${root}/backoffice`);
      await page.getByLabel('Email', { exact: true }).fill('staff@example.test');
      await page.getByLabel('Password', { exact: true }).fill('mock-password');
      await page.screenshot({ path: `${evidence}/backoffice-desktop.png`, fullPage: true });
      await page.setViewportSize({ width: 390, height: 844 });
      await page.screenshot({ path: `${evidence}/backoffice-mobile.png`, fullPage: true });
      await page.getByRole('button', { name: 'Sign in', exact: true }).click();
      await page.getByRole('heading', { name: 'Platform staff access required' }).waitFor();
      await page.getByRole('button', { name: 'Sign out and use another account' }).click();
      await page.getByRole('button', { name: 'Sign in', exact: true }).waitFor();
    });

    await test('tenant switch drops old cohort selections and delayed responses', async (page) => {
      let release;
      const delayed = new Promise((resolve) => { release = resolve; });
      await mock(page, async (path) => {
        if (path === '/portal/1/cohorts') return { body: [cohort(11, 'Old cohort')] };
        if (path === '/portal/2/cohorts') return { body: [cohort(22, 'New cohort')] };
        if (path.includes('/cohorts/11/assignment')) { await delayed; return { body: { plans: [{ id: 1, code: 'OLD PLAN', label: 'Old' }], activities: [], selected_plan_ids: [], selected_activity_ids: [] } }; }
        if (path.includes('/cohorts/22/assignment')) return { body: { plans: [{ id: 2, code: 'NEW PLAN', label: 'New' }], activities: [], selected_plan_ids: [], selected_activity_ids: [] } };
        if (path.endsWith('/progress')) return { body: null };
      });
      await portal(page);
      await page.getByRole('button', { name: /Old cohort/ }).waitFor();
      await page.getByLabel('Institution', { exact: true }).selectOption('2');
      await page.getByText('NEW PLAN', { exact: true }).waitFor();
      release();
      await page.waitForTimeout(100);
      assert.equal(await page.getByText('OLD PLAN', { exact: true }).count(), 0);
      assert.deepEqual(await page.locator('.roster-select select').evaluateAll((nodes) => nodes.map((node) => node.value)), ['22', '22']);
    });

    await test('cohort switch ignores delayed assignment and roster responses', async (page) => {
      let release;
      const delayed = new Promise((resolve) => { release = resolve; });
      await mock(page, async (path) => {
        if (path === '/portal/1/cohorts') return { body: [cohort(11, 'First'), cohort(12, 'Second')] };
        if (path.endsWith('/progress')) return { body: null };
        if (path.endsWith('/assignment')) {
          if (path.includes('/11/')) await delayed;
          return { body: { plans: [{ id: path.includes('/11/') ? 11 : 12, code: path.includes('/11/') ? 'STALE PLAN' : 'CURRENT PLAN', label: 'Test' }], activities: [], selected_plan_ids: [], selected_activity_ids: [] } };
        }
        if (path.includes('/11/participants')) {
          await delayed;
          return { body: [{ participant_id: 1, user_id: 1, identifier: 'stale@example.test', enrollment_status: 'active', enrolled_at: '2026-10-02', consent_status: 'granted' }] };
        }
      });
      await portal(page);
      await page.locator('.assignment-panel .roster-select select').selectOption('12');
      await page.locator('.roster-panel .roster-select select').selectOption('12');
      await page.getByText('CURRENT PLAN', { exact: true }).waitFor();
      release();
      await page.waitForTimeout(100);
      assert.equal(await page.getByText('STALE PLAN', { exact: true }).count(), 0);
      assert.equal(await page.getByText('stale@example.test', { exact: true }).count(), 0);
    });

    await test('admin creates a practice activity from validated vocabulary', async (page) => {
      let created = false;
      await mock(page, (path, request) => {
        if (path === '/vocabulary/1/signs') return { body: [{ id: 5, concept_id: 1, sign_id: 'hello', gloss: 'HELLO', language: 'lsb', status: 'validated' }] };
        if (path === '/vocabulary/1/plans') return { body: [{ id: 6, concept_id: 1, code: 'hello-plan', items: [], status: 'validated' }] };
        if (path === '/portal/1/activities') {
          assert.equal(request.method(), 'POST');
          assert.deepEqual(request.postDataJSON(), { plan_id: 6, sign_id: 5 });
          created = true; return { status: 201, body: { id: 10 } };
        }
      });
      await portal(page);
      await page.getByLabel('Validated plan', { exact: false }).selectOption('6');
      await page.getByLabel('Validated sign', { exact: false }).selectOption('5');
      await page.getByRole('button', { name: 'Create activity', exact: true }).click();
      await page.getByText('Practice activity 10 created. Assign it to a cohort below.').waitFor();
      assert.equal(created, true);
    });

    await test('plan editor loads variants without visiting Signs and keeps keyboard focus', async (page) => {
      await mock(page, (path) => {
        if (path === '/vocabulary/1/signs') return { body: [{ id: 5, concept_id: 1, sign_id: 'hello', gloss: 'HELLO', language: 'lsb', status: 'validated' }] };
        if (path === '/vocabulary/1/concepts') return { body: [{ id: 1, code: 'hello', label: 'Hello', description: '' }] };
        if (path === '/vocabulary/1/signs/5/variants') return { body: [{ id: 8, sign_id: 5, variant_code: 'regional', label: 'Regional', hamnosys: '' }] };
      });
      await page.goto(`${root}/portal`);
      await page.getByLabel('Institution', { exact: true }).selectOption('1');
      await page.getByRole('button', { name: 'Sign plans' }).click();
      assert.equal(await page.getByRole('button', { name: 'Sign plans' }).getAttribute('aria-current'), 'page');
      await page.getByRole('button', { name: 'New plan' }).click();
      await page.getByLabel('Variant for HELLO').selectOption('8');
      await page.getByLabel('Filter sign plans').focus();
      assert.notEqual(await page.getByLabel('Filter sign plans').evaluate((node) => getComputedStyle(node).outlineStyle), 'none');
    });
    console.log(`${passed} browser interaction tests passed; screenshots: ${evidence}`);
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
