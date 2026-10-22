const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const {PassThrough} = require('node:stream');
const source = fs.readFileSync(path.resolve(process.env.PIPELINE_BUNDLE_DIR || path.join(__dirname, '../build'), 'index-DQV9sVEn.cjs'), 'utf8');
const begin = source.indexOf('    async _uploadChunk(options, retryCount = this.options.retryTimes) {');
assert(begin >= 0, 'actual uploader method must exist');
const end = source.indexOf('    /**', begin + 20);
assert(end > begin, 'actual uploader method end must exist');
const method = source.slice(begin, end);
const input = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'upload-stream-test-')), 'fixture.flv');
fs.writeFileSync(input, Buffer.alloc(1024 * 1024, 7));

(async () => {
  let count = 0;
  try {
    for (const scenario of ['success', 'failure', 'retry', 'cancel', 'throttle-failure']) {
      const opened = [], throttles = [];
      class Throttle extends PassThrough { constructor() { super(); throttles.push(this); } }
      const api = vm.runInNewContext(`({${method}})`, {
        createReadStream: (filePath, start, chunkSize, size) => {
          const stream = fs.createReadStream(filePath, {start, end: Math.min(start + chunkSize - 1, size - 1)});
          opened.push(stream);
          return [stream, chunkSize];
        }, 'Throttle$1': Throttle,
      });
      api.options = {retryTimes: scenario === 'retry' ? 1 : scenario === 'cancel' ? 3 : 0, retryDelay: 1, limitRate: scenario.startsWith('throttle') ? 1 : 0};
      api.chunkTasks = {1: {status: 'pending'}};
      api.sleep = async () => {};
      api.uploadChunkApi = async (_, stream) => {
        if (scenario === 'success') { for await (const _ of stream) {} return; }
        const error = new Error('simulated network interruption');
        if (scenario === 'cancel') error.code = 'ERR_CANCELED';
        throw error;
      };
      let result, failure;
      try {
        result = await api._uploadChunk({filePath: input, start: 0, chunk_size: 1024 * 1024, size: 1024 * 1024, chunk: 0});
      } catch (error) { failure = error; }
      await new Promise(resolve => setTimeout(resolve, 30));
      try {
        assert(opened.length > 0);
        assert(opened.every(s => s.destroyed && s.closed), `${scenario}: upload source FD must be closed`);
        assert(throttles.every(s => s.destroyed), `${scenario}: throttle must be destroyed`);
        if (scenario === 'retry') assert.equal(opened.length, 2);
        if (scenario === 'success') { assert.equal(result, 1); assert.equal(failure, undefined); }
        else if (scenario === 'cancel') {
          assert.equal(opened.length, 1); assert.equal(failure, undefined);
          assert.equal(api.chunkTasks[1].status, 'abort');
        } else {
          assert(failure); assert.equal(api.chunkTasks[1].status, 'error');
        }
        console.log(`PASS ${scenario}: ${opened.length} source stream(s) closed`);
        count++;
      } finally {
        opened.forEach(s => s.destroy());
        throttles.forEach(s => s.destroy());
      }
    }
    console.log(`${count} actual uploader method checks passed`);
  } finally { fs.rmSync(path.dirname(input), {recursive: true}); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
