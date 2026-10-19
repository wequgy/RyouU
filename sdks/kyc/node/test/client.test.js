const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');

const {
  UncloneKycClient,
  verifyWebhook,
  WebhookVerificationError,
  AuthenticationError,
  NotFoundError,
  ConflictError,
  RateLimitError,
} = require('../dist/index.js');

describe('UncloneKycClient', () => {
  test('initialization requires apiKey', () => {
    assert.throws(() => new UncloneKycClient({}), /apiKey/);
    const client = new UncloneKycClient({ apiKey: 'test_key', baseUrl: 'http://localhost:8000/' });
    assert.equal(client.baseUrl, 'http://localhost:8000');
  });

  describe('API operations with mocked fetch', () => {
    let originalFetch;

    beforeEach(() => {
      originalFetch = global.fetch;
    });

    afterEach(() => {
      global.fetch = originalFetch;
    });

    test('createVerification and getVerification', async () => {
      global.fetch = async (url, options) => {
        assert.equal(options.headers['Authorization'], 'Bearer test_key');
        if (url.endsWith('/v1/verifications') && options.method === 'POST') {
          return {
            ok: true,
            status: 201,
            json: async () => ({
              id: 'ver_node_1',
              status: 'created',
              policy: 'strict',
              expires_at: 1792180000,
              flow_url: 'https://api.unclone.ai/flow?v=ver_node_1&t=tok123',
            }),
          };
        }
        if (url.endsWith('/v1/verifications/ver_node_1') && options.method === 'GET') {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              id: 'ver_node_1',
              reference_id: 'ref_1',
              status: 'completed',
              policy: 'strict',
              decision: 'approved',
              final_decision: 'approved',
              trust: 0.95,
              reasons: [],
              results: [],
            }),
          };
        }
        return { ok: false, status: 404, json: async () => ({}) };
      };

      const client = new UncloneKycClient({ apiKey: 'test_key', baseUrl: 'https://api.unclone.ai' });
      const session = await client.createVerification({
        referenceId: 'ref_1',
        expected: { name: 'Bob' },
        policy: 'strict',
        idempotencyKey: 'idemp_node_1',
      });

      assert.equal(session.id, 'ver_node_1');
      assert.equal(session.status, 'created');

      const result = await client.getVerification('ver_node_1');
      assert.equal(result.id, 'ver_node_1');
      assert.equal(result.decision, 'approved');
      assert.equal(result.trust, 0.95);
    });

    test('reviewVerification and deleteVerification', async () => {
      global.fetch = async (url, options) => {
        if (url.endsWith('/v1/verifications/ver_node_1/review') && options.method === 'POST') {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              id: 'ver_node_1',
              decision: 'needs_review',
              final_decision: 'approved',
            }),
          };
        }
        if (url.endsWith('/v1/verifications/ver_node_1') && options.method === 'DELETE') {
          return { ok: true, status: 204 };
        }
        return { ok: false, status: 400 };
      };

      const client = new UncloneKycClient({ apiKey: 'test_key' });
      const reviewed = await client.reviewVerification('ver_node_1', { decision: 'approved', note: 'Verified in person' });
      assert.equal(reviewed.final_decision, 'approved');

      const deleted = await client.deleteVerification('ver_node_1');
      assert.equal(deleted, true);
    });

    test('typed error handling', async () => {
      global.fetch = async (url) => {
        if (url.endsWith('/auth_err')) return { ok: false, status: 401, json: async () => ({ detail: 'Unauthorized' }) };
        if (url.endsWith('/not_found')) return { ok: false, status: 404, json: async () => ({ detail: 'Not Found' }) };
        if (url.endsWith('/conflict')) return { ok: false, status: 409, text: async () => 'State conflict' };
        if (url.endsWith('/rate_limit')) return { ok: false, status: 429, json: async () => ({ detail: 'Too Many Requests' }) };
        return { ok: true, status: 200, json: async () => ({}) };
      };

      const client = new UncloneKycClient({ apiKey: 'test_key' });

      await assert.rejects(() => client.getVerification('auth_err'), AuthenticationError);
      await assert.rejects(() => client.getVerification('not_found'), NotFoundError);
      await assert.rejects(() => client.getVerification('conflict'), ConflictError);
      await assert.rejects(() => client.getVerification('rate_limit'), RateLimitError);
    });
  });

  describe('webhook verification', () => {
    test('verifyWebhook verifies valid HMAC signature', () => {
      const secret = 'whsec_test_secret_abc123';
      const payload = JSON.stringify({ type: 'verification.completed', data: { id: 'ver_1', decision: 'approved' } });
      const now = Math.floor(Date.now() / 1000);

      const hmac = crypto.createHmac('sha256', secret);
      hmac.update(`${now}.`);
      hmac.update(Buffer.from(payload));
      const mac = hmac.digest('hex');
      const header = `t=${now},v1=${mac}`;

      const event = verifyWebhook(payload, header, secret, 300);
      assert.equal(event.type, 'verification.completed');
      assert.equal(event.data.id, 'ver_1');
    });

    test('verifyWebhook rejects tampered payload', () => {
      const secret = 'whsec_test_secret_abc123';
      const payload = JSON.stringify({ type: 'verification.completed' });
      const now = Math.floor(Date.now() / 1000);

      const hmac = crypto.createHmac('sha256', secret);
      hmac.update(`${now}.`);
      hmac.update(Buffer.from(payload));
      const header = `t=${now},v1=${hmac.digest('hex')}`;

      assert.throws(
        () => verifyWebhook('{"tampered": true}', header, secret, 300),
        WebhookVerificationError
      );
    });

    test('verifyWebhook rejects replayed/expired timestamps', () => {
      const secret = 'whsec_test_secret_abc123';
      const payload = JSON.stringify({ type: 'verification.completed' });
      const expiredTs = Math.floor(Date.now() / 1000) - 600;

      const hmac = crypto.createHmac('sha256', secret);
      hmac.update(`${expiredTs}.`);
      hmac.update(Buffer.from(payload));
      const header = `t=${expiredTs},v1=${hmac.digest('hex')}`;

      assert.throws(
        () => verifyWebhook(payload, header, secret, 300),
        WebhookVerificationError
      );
    });
  });
});
