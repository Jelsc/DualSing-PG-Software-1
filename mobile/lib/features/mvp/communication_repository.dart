import 'dart:convert';

import 'package:http/http.dart' as http;

class CommunicationStep {
  const CommunicationStep({
    required this.signId,
    required this.clipKey,
    required this.assetAvailable,
    required this.gloss,
  });
  final String signId;
  final String clipKey;
  final bool assetAvailable;
  final String gloss;
}

class CommunicationResult {
  const CommunicationResult({
    required this.status,
    required this.steps,
    this.reason,
  });
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
        reason:
            'Iniciá sesión y configurá una institución para usar comunicación.',
      );
}

abstract interface class Playback {
  Future<void> play(List<CommunicationStep> steps);
}

class UnavailablePlayback implements Playback {
  @override
  Future<void> play(List<CommunicationStep> steps) async {}
}

class HttpCommunicationRepository implements CommunicationRepository {
  HttpCommunicationRepository(
    this.baseUri,
    this.accessToken, {
    http.Client? client,
  }) : _client = client ?? http.Client();
  final Uri baseUri;
  final String accessToken;
  final http.Client _client;

  @override
  Future<CommunicationResult> resolve(String input) async {
    final response = await _client.post(
      baseUri,
      headers: {
        'Authorization': 'Bearer $accessToken',
        'Content-Type': 'application/json',
      },
      body: jsonEncode({'input': input}),
    );
    if (response.statusCode >= 400)
      throw http.ClientException(
        'Communication request failed (${response.statusCode})',
      );
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return CommunicationResult(
      status: body['status'] as String,
      reason: body['reason'] as String?,
      steps: ((body['steps'] as List<dynamic>?) ?? [])
          .map(
            (item) => CommunicationStep(
              signId: item['stable_sign_id'] as String,
              clipKey: item['clip_key'] as String,
              assetAvailable: item['asset_available'] as bool,
              gloss: item['gloss'] as String,
            ),
          )
          .toList(),
    );
  }
}
