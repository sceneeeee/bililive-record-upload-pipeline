const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.resolve(process.env.PIPELINE_BUNDLE_DIR || path.join(__dirname, '../build'), 'index-ZJeYopVC.cjs'), 'utf8');
const wrapper = source.slice(source.indexOf('    uploadRuns = new WeakMap();'), source.indexOf('    handleLiveOnce = async'));
const Cls = vm.runInNewContext(`(class { ${wrapper} })`);
(async () => {
  const instance = new Cls(), live = {};
  let running = 0, maximum = 0, calls = 0, release;
  instance.handleLiveOnce = async () => {
    running++; maximum = Math.max(maximum, running); calls++;
    if (calls === 1) await new Promise(resolve => { release = resolve; });
    running--;
  };
  const first = instance.handleLive(live);
  await new Promise(resolve => setImmediate(resolve));
  const second = instance.handleLive(live);
  const third = instance.handleLive(live);
  release(); await Promise.all([first, second, third]);
  assert.equal(maximum, 1); assert.equal(calls, 2);
  console.log('PASS concurrent close/timer requests serialize; new segment runs after current upload');
  instance.handleLiveOnce = async () => { throw new Error('fixture'); };
  await instance.handleLive(live).catch(() => {});
  assert.equal(instance.uploadRuns.has(live), false);
  console.log('PASS scheduler failure releases lock and does not retry forever');
  for (const types of [['handled','raw'], ['raw','handled'], ['handled',undefined], [undefined,'raw']]) {
    const scheduler = new Cls(), requested = []; let releaseFirst;
    scheduler.handleLiveOnce = async (_, type) => {
      requested.push(type);
      if (requested.length === 1) await new Promise(resolve => { releaseFirst = resolve; });
    };
    const a = scheduler.handleLive(live, types[0]);
    await new Promise(resolve => setImmediate(resolve));
    const b = scheduler.handleLive(live, types[1]);
    releaseFirst(); await Promise.all([a,b]);
    assert.deepEqual(requested, types, 'all requested upload channels must survive');
  }
  console.log('PASS handled/raw and all-channel requests retain their type in both orders');
  const independent = new Cls(); let active = 0, peak = 0;
  independent.handleLiveOnce = async () => {
    active++; peak = Math.max(peak, active);
    await new Promise(resolve => setImmediate(resolve)); active--;
  };
  await Promise.all([independent.handleLive({}), independent.handleLive({})]);
  assert.equal(peak, 2);
  console.log('PASS independent lives can schedule concurrently');
  const begin = source.indexOf('    async processEvent(partId, options, config) {');
  const end = source.indexOf('    /**', begin + 20);
  const callsReady = [];
  const handler = vm.runInNewContext(`({${source.slice(begin,end)}})`, {
    PathResolver: {getDanmuPath: () => undefined},
    'index$1': {logObj: {debug() {}, error() {}}},
  });
  Object.assign(handler, {
    shouldSkipProcessing: () => false,
    liveManager: {findBy: () => ({live, part: {filePath: 'fixture.flv'}})},
    processConversion: async () => {}, collectTasks() {},
    processMediaFiles: async () => ({conversionSuccessful: false, danmuConversionSuccessful: false}),
    handlePostProcessing: async () => callsReady.push('ready'),
    handleLive: () => { callsReady.push('upload'); return new Promise(() => {}); },
  });
  await handler.processEvent('part', {filePath: 'fixture.flv'}, {});
  assert.deepEqual(callsReady, ['ready', 'upload']);
  console.log('PASS ready file schedules upload immediately; processing does not wait for upload');
})().catch(error => { console.error(error); process.exitCode = 1; });
