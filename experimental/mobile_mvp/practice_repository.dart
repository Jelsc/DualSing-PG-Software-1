import 'dart:convert';
import 'dart:io';

class PracticeActivity {
  const PracticeActivity({required this.id, required this.prompt, required this.signId, required this.modelVersion});
  final int id;
  final String prompt;
  final String signId;
  final String modelVersion;
}

class PracticeResult {
  const PracticeResult(this.value, this.explanation);
  final String value;
  final String explanation;
}

abstract interface class PracticeRepository {
  Future<List<PracticeActivity>> listActivities();
  Future<PracticeResult> submit(PracticeActivity activity);
}

class ConfigurationPracticeRepository implements PracticeRepository {
  const ConfigurationPracticeRepository();

  @override
  Future<List<PracticeActivity>> listActivities() async => const [];

  @override
  Future<PracticeResult> submit(PracticeActivity activity) async =>
      const PracticeResult('unknown', 'Iniciá sesión para registrar un intento.');
}

class HttpPracticeRepository implements PracticeRepository {
  HttpPracticeRepository(this.baseUri, this.accessToken);

  final Uri baseUri;
  final String accessToken;

  @override
  Future<List<PracticeActivity>> listActivities() async {
    final response = await _request(baseUri.resolve('activities')) as List<dynamic>;
    return response
        .map((item) => PracticeActivity(
              id: item['id'] as int,
              prompt: item['prompt'] as String,
              signId: item['sign_id'] as String,
              modelVersion: item['model_version'] as String,
            ))
        .toList();
  }

  @override
  Future<PracticeResult> submit(PracticeActivity activity) async {
    final response = await _request(
      baseUri.resolve('activities/${activity.id}/attempt'),
      method: 'POST',
      body: {'result': 'unknown'},
    ) as Map<String, dynamic>;
    return PracticeResult(
      response['result'] as String,
      '${response['evaluation_mode']} · ${response['inference_source']}',
    );
  }

  Future<dynamic> _request(
    Uri uri, {
    String method = 'GET',
    Map<String, dynamic>? body,
  }) async {
    final client = HttpClient();
    try {
      final request = method == 'POST' ? await client.postUrl(uri) : await client.getUrl(uri);
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $accessToken');
      request.headers.contentType = ContentType.json;
      if (body != null) request.write(jsonEncode(body));
      final response = await request.close();
      final decoded = jsonDecode(await response.transform(utf8.decoder).join());
      if (response.statusCode >= 400) {
        throw HttpException('Practice request failed', uri: uri);
      }
      return decoded;
    } finally {
      client.close();
    }
  }
}

class InMemoryPracticeRepository implements PracticeRepository {
  const InMemoryPracticeRepository();
  @override
  Future<List<PracticeActivity>> listActivities() async => const [PracticeActivity(id: 1, prompt: 'Practica el saludo', signId: 'greet-v1', modelVersion: 'synthetic-gru-v1')];

  @override
  Future<PracticeResult> submit(PracticeActivity activity) async => const PracticeResult('unknown', 'El scaffold sintético no puede determinar el gesto todavía.');
}
