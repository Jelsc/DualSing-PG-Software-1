import 'dart:convert';
import 'dart:io';

class CommunicationStep {
  const CommunicationStep({required this.signId, required this.clipKey, required this.assetAvailable, required this.gloss});
  final String signId;
  final String clipKey;
  final bool assetAvailable;
  final String gloss;
}

class CommunicationResult {
  const CommunicationResult({required this.status, required this.steps, this.reason});
  final String status;
  final List<CommunicationStep> steps;
  final String? reason;
}

abstract interface class CommunicationRepository {
  Future<CommunicationResult> resolve(String input);
}

class ConfigurationCommunicationRepository implements CommunicationRepository {
  const ConfigurationCommunicationRepository();

  @override
  Future<CommunicationResult> resolve(String input) async =>
      const CommunicationResult(
        status: 'configuration_required',
        steps: [],
        reason: 'Iniciá sesión y configurá una institución para usar comunicación.',
      );
}

abstract interface class Playback {
  Future<void> play(List<CommunicationStep> steps);
}

class UnavailablePlayback implements Playback {
  @override
  Future<void> play(List<CommunicationStep> steps) async {}
}

class InMemoryCommunicationRepository implements CommunicationRepository {
  const InMemoryCommunicationRepository();
  @override
  Future<CommunicationResult> resolve(String input) async {
    if (input.trim().toLowerCase() != 'hello') {
      return const CommunicationResult(status: 'unsupported_input', steps: [], reason: 'No está en el catálogo controlado.');
    }
    return const CommunicationResult(
      status: 'missing_clip_mapping',
      steps: [CommunicationStep(signId: 'greet-v1', clipKey: 'sign:greet-v1', assetAvailable: false, gloss: 'HELLO')],
      reason: 'El MVP no incluye clips GLB reales.',
    );
  }
}

class HttpCommunicationRepository implements CommunicationRepository {
  HttpCommunicationRepository(this.baseUri, this.accessToken);
  final Uri baseUri;
  final String accessToken;

  @override
  Future<CommunicationResult> resolve(String input) async {
    final client = HttpClient();
    try {
      final request = await client.postUrl(baseUri);
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $accessToken');
      request.headers.contentType = ContentType.json;
      request.write(jsonEncode({'input': input}));
      final response = await request.close();
      final body = jsonDecode(await response.transform(utf8.decoder).join()) as Map<String, dynamic>;
      return CommunicationResult(
        status: body['status'] as String,
        reason: body['reason'] as String?,
        steps: ((body['steps'] as List<dynamic>?) ?? []).map((item) => CommunicationStep(signId: item['stable_sign_id'] as String, clipKey: item['clip_key'] as String, assetAvailable: item['asset_available'] as bool, gloss: item['gloss'] as String)).toList(),
      );
    } finally {
      client.close();
    }
  }
}
