const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const { pollVerificationStatus } = require('../dist/polling.js');
const { TimeoutError } = require('../dist/errors.js');

describe('Polling Logic', () => {
  test('polls until completed and returns mapped verdict', async () => {
    let callCount = 0;
    const mockFetch = async () => {
      callCount++;
      if (callCount < 3) {
        return {
          ok: true,
          json: async () => ({ id: 'ver_poll', status: 'processing', decision: null }),
        };
      }
      return {
        ok: true,
        json: async () => ({
          id: 'ver_poll',
          status: 'completed',
          decision: 'approved',
          final_decision: 'approved',
          trust: 0.99,
        }),
      };
    };

    const res = await pollVerificationStatus({
      backendUrl: 'http://backend.test',
      verificationId: 'ver_poll',
      initialIntervalMs: 10,
      maxIntervalMs: 50,
      timeoutMs: 5000,
      fetchFn: mockFetch,
    });

    assert.equal(callCount, 3);
    assert.equal(res.status, 'SUCCESS');
    assert.equal(res.verificationId, 'ver_poll');
  });

  test('times out if decision is not reached', async () => {
    const mockFetch = async () => ({
      ok: true,
      json: async () => ({ id: 'ver_poll', status: 'processing' }),
    });

    await assert.rejects(
      () =>
        pollVerificationStatus({
          backendUrl: 'http://backend.test',
          verificationId: 'ver_poll',
          initialIntervalMs: 10,
          maxAttempts: 3,
          fetchFn: mockFetch,
        }),
      TimeoutError
    );
  });
});
