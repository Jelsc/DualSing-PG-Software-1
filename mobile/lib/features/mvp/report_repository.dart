import 'dart:convert';

import 'package:http/http.dart' as http;

class PilotReport {
  const PilotReport({
    required this.enrolled,
    required this.attempts,
    required this.correct,
    required this.incorrect,
    required this.unknown,
    required this.unknownRate,
    required this.completion,
    required this.p50Latency,
    required this.p95Latency,
    this.available = true,
    this.message,
  });
  final int enrolled;
  final int attempts;
  final int correct;
  final int incorrect;
  final int unknown;
  final double unknownRate;
  final int completion;
  final int? p50Latency;
  final int? p95Latency;
  final bool available;
  final String? message;
}

abstract interface class ReportRepository {
  Future<PilotReport> load();
}

class ConfigurationReportRepository implements ReportRepository {
  const ConfigurationReportRepository();

  @override
  Future<PilotReport> load() async => const PilotReport(
    enrolled: 0,
    attempts: 0,
    correct: 0,
    incorrect: 0,
    unknown: 0,
    unknownRate: 0,
    completion: 0,
    p50Latency: null,
    p95Latency: null,
    available: false,
    message:
        'Iniciá sesión y configurá un piloto para consultar métricas reales.',
  );
}

class HttpReportRepository implements ReportRepository {
  HttpReportRepository(this.baseUri, this.accessToken, {http.Client? client})
    : _client = client ?? http.Client();
  final Uri baseUri;
  final String accessToken;
  final http.Client _client;

  @override
  Future<PilotReport> load() async {
    final response = await _client.get(
      baseUri,
      headers: {'Authorization': 'Bearer $accessToken'},
    );
    if (response.statusCode >= 400)
      throw http.ClientException(
        'Report request failed (${response.statusCode})',
      );
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final attempts = body['attempts'] as Map<String, dynamic>;
    final participation = body['participation'] as Map<String, dynamic>;
    final latency = body['latency_ms'] as Map<String, dynamic>;
    final eligible = participation['eligible'] as int;
    return PilotReport(
      enrolled: participation['enrolled'] as int,
      attempts: attempts['total'] as int,
      correct: attempts['correct'] as int,
      incorrect: attempts['incorrect'] as int,
      unknown: attempts['unknown'] as int,
      unknownRate: (attempts['unknown_rate'] as num).toDouble(),
      completion: eligible == 0
          ? 0
          : ((participation['participants_with_attempts'] as int) /
                    eligible *
                    100)
                .round(),
      p50Latency: latency['p50'] as int?,
      p95Latency: latency['p95'] as int?,
    );
  }
}
