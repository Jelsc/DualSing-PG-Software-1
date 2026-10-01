import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:dualsign_mobile/features/mvp/communication_repository.dart';
import 'package:dualsign_mobile/features/mvp/cohort_repository.dart';
import 'package:dualsign_mobile/features/mvp/mvp_repositories.dart';
import 'package:dualsign_mobile/features/mvp/practice_repository.dart';
import 'package:dualsign_mobile/features/mvp/report_repository.dart';

void main() {
  test(
    'parses activities and submits the explicitly selected synthetic result',
    () async {
      final client = MockClient((request) async {
        expect(request.headers['authorization'], 'Bearer access');
        if (request.method == 'GET')
          return http.Response(
            jsonEncode([
              {
                'id': 4,
                'prompt': 'HELLO',
                'sign_id': 'greet-v1',
                'model_version': 'synthetic-v1',
              },
            ]),
            200,
          );
        expect(jsonDecode(request.body)['result'], 'correct');
        return http.Response(
          jsonEncode({
            'result': 'correct',
            'latency_ms': 120,
            'evaluation_mode': 'synthetic_scaffold',
            'inference_source': 'controlled_client',
            'consent_status': 'not_required',
          }),
          200,
        );
      });
      final repository = HttpPracticeRepository(
        Uri.parse('https://api.test/activities/'),
        'access',
        client: client,
      );
      final activity = (await repository.listActivities()).single;
      final result = await repository.submit(activity, 'correct');
      expect(result.value, 'correct');
      expect(result.latencyMs, 120);
      expect(result.evaluationMode, 'synthetic_scaffold');
    },
  );

  test('parses complete empty-safe report metrics', () async {
    final repository = HttpReportRepository(
      Uri.parse('https://api.test/report'),
      'access',
      client: MockClient(
        (_) async => http.Response(
          jsonEncode({
            'participation': {
              'enrolled': 0,
              'eligible': 0,
              'participants_with_attempts': 0,
            },
            'attempts': {
              'total': 0,
              'correct': 0,
              'incorrect': 0,
              'unknown': 0,
              'unknown_rate': 0,
            },
            'latency_ms': {'p50': null, 'p95': null},
          }),
          200,
        ),
      ),
    );
    final report = await repository.load();
    expect(report.attempts, 0);
    expect(report.completion, 0);
    expect(report.p50Latency, isNull);
  });

  test(
    'preserves controlled communication clip keys and asset availability',
    () async {
      final repository = HttpCommunicationRepository(
        Uri.parse('https://api.test/resolve'),
        'access',
        client: MockClient((request) async {
          expect(jsonDecode(request.body)['input'], 'hello');
          return http.Response(
            jsonEncode({
              'status': 'missing_clip_mapping',
              'steps': [
                {
                  'stable_sign_id': 'greet-v1',
                  'clip_key': 'sign:greet-v1',
                  'asset_available': false,
                  'gloss': 'HELLO',
                },
              ],
            }),
            200,
          );
        }),
      );
      final result = await repository.resolve('hello');
      expect(result.steps.single.clipKey, 'sign:greet-v1');
      expect(result.steps.single.assetAvailable, isFalse);
    },
  );

  test('posts self-enrollment to the configured cohort boundary', () async {
    final repository = HttpPilotEnrollmentRepository(
      Uri.parse('https://api.test/participants'),
      'access',
      client: MockClient((request) async {
        expect(request.method, 'POST');
        return http.Response(
          '{"cohort_id":9,"user_id":3,"enrolled":true}',
          201,
        );
      }),
    );
    final result = await repository.enroll();
    expect(result.cohortId, 9);
    expect(result.enrolled, isTrue);
  });

  test('loads only server-backed safe cohort metadata', () async {
    final repository = HttpCohortRepository(
      Uri.parse('https://api.test/api/'),
      'access',
      client: MockClient((request) async {
        expect(request.url.path, '/api/mobile/mvp/7/pilots/cohorts');
        expect(request.headers['authorization'], 'Bearer access');
        return http.Response(
          jsonEncode([
            {
              'id': 9,
              'name': 'Spring pilot',
              'start_date': '2026-01-01',
              'end_date': null,
              'status': 'planned',
              'consent_required': true,
              'enrolled': false,
            },
          ]),
          200,
        );
      }),
    );
    final cohort = (await repository.list(7)).single;
    expect(cohort.id, 9);
    expect(cohort.status, 'planned');
    expect(cohort.enrolled, isFalse);
  });
}
