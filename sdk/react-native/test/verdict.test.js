const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const { mapBackendVerdict } = require('../dist/verdict.js');

describe('Verdict Mapping Rules', () => {
  test('approved maps to SUCCESS', () => {
    const res = mapBackendVerdict({
      id: 'ver_1',
      status: 'completed',
      decision: 'approved',
      final_decision: 'approved',
      trust: 0.95,
      reasons: [],
    });
    assert.equal(res.status, 'SUCCESS');
    assert.equal(res.verificationId, 'ver_1');
    assert.equal(res.riskScore, 0.05);
  });

  test('needs_review maps to IN_REVIEW', () => {
    const res = mapBackendVerdict({
      id: 'ver_2',
      status: 'completed',
      decision: 'needs_review',
      trust: 0.70,
      reasons: ['face_match: borderline'],
    });
    assert.equal(res.status, 'IN_REVIEW');
    assert.equal(res.riskScore, 0.30);
    assert.deepEqual(res.reasons, ['face_match: borderline']);
  });

  test('rejected_recommended maps to IN_REVIEW (requires human decision)', () => {
    const res = mapBackendVerdict({
      id: 'ver_3',
      status: 'completed',
      decision: 'rejected_recommended',
      trust: 0.10,
      reasons: ['face_match: different person'],
    });
    assert.equal(res.status, 'IN_REVIEW');
  });

  test('human review rejected maps to FAILED', () => {
    const res = mapBackendVerdict({
      id: 'ver_4',
      status: 'reviewed',
      decision: 'needs_review',
      final_decision: 'rejected',
      trust: 0.65,
    });
    assert.equal(res.status, 'FAILED');
  });

  test('human review approved overrides rejection to SUCCESS', () => {
    const res = mapBackendVerdict({
      id: 'ver_5',
      status: 'reviewed',
      decision: 'rejected_recommended',
      final_decision: 'approved',
      trust: 0.20,
    });
    assert.equal(res.status, 'SUCCESS');
  });

  test('status="completed" alone without approved decision is NEVER SUCCESS', () => {
    const res = mapBackendVerdict({
      id: 'ver_6',
      status: 'completed',
      decision: null,
      final_decision: null,
    });
    assert.notEqual(res.status, 'SUCCESS');
    assert.equal(res.status, 'IN_REVIEW');
  });
});
