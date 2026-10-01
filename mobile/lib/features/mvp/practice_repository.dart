import 'dart:convert';

import 'package:http/http.dart' as http;

class PracticeActivity {
  const PracticeActivity({
    required this.id,
    required this.prompt,
    required this.signId,
    required this.modelVersion,
  });
  final int id;
  final String prompt;
  final String signId;
  final String modelVersion;
}

class PracticeResult {
  const PracticeResult({
    required this.value,
    required this.latencyMs,
    required this.evaluationMode,
    required this.inferenceSource,
  });
  final String value;
  final int? latencyMs;
  final String evaluationMode;
  final String inferenceSource;
}

abstract interface class PracticeRepository {
  Future<List<PracticeActivity>> listActivities();
  Future<PracticeResult> submit(
    PracticeActivity activity,
    String result, {
    int? latencyMs,
  });
}

class ConfigurationPracticeRepository implements PracticeRepository {
  const ConfigurationPracticeRepository();

  @override
  Future<List<PracticeActivity>> listActivities() async => const [];

  @override
  Future<PracticeResult> submit(
    PracticeActivity activity,
    String result, {
    int? latencyMs,
  }) async => throw StateError(
    'Authentication is required to submit a practice attempt.',
  );
}

class HttpPracticeRepository implements PracticeRepository {
  HttpPracticeRepository(this.baseUri, this.accessToken, {http.Client? client})
    : _client = client ?? http.Client();
  final Uri baseUri;
  final String accessToken;
  final http.Client _client;

  @override
  Future<List<PracticeActivity>> listActivities() async {
    final response =
        await _request(baseUri.resolve('activities')) as List<dynamic>;
    return response
        .map(
          (item) => PracticeActivity(
            id: item['id'] as int,
            prompt: item['prompt'] as String,
            signId: item['sign_id'] as String,
            modelVersion: item['model_version'] as String,
          ),
        )
        .toList();
  }

  @override
  Future<PracticeResult> submit(
    PracticeActivity activity,
    String result, {
    int? latencyMs,
  }) async {
    final response =
        await _request(
              baseUri.resolve('activities/${activity.id}/attempt'),
              method: 'POST',
              body: {'result': result, 'latency_ms': latencyMs},
            )
            as Map<String, dynamic>;
    return PracticeResult(
      value: response['result'] as String,
      latencyMs: response['latency_ms'] as int?,
      evaluationMode: response['evaluation_mode'] as String,
      inferenceSource: response['inference_source'] as String,
    );
  }

  Future<dynamic> _request(
    Uri uri, {
    String method = 'GET',
    Map<String, dynamic>? body,
  }) async {
    final response = method == 'POST'
        ? await _client.post(
            uri,
            headers: {
              'Authorization': 'Bearer $accessToken',
              'Content-Type': 'application/json',
            },
            body: jsonEncode(body),
          )
        : await _client.get(
            uri,
            headers: {'Authorization': 'Bearer $accessToken'},
          );
    if (response.statusCode >= 400)
      throw http.ClientException(
        'Practice request failed (${response.statusCode})',
      );
    return jsonDecode(response.body);
  }
}
