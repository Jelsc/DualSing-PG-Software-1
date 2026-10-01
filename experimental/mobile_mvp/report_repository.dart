import 'dart:convert';
import 'dart:io';

class PilotReport {
  const PilotReport({required this.enrolled, required this.attempts, required this.unknownRate, this.available = true, this.message});
  final int enrolled;
  final int attempts;
  final double unknownRate;
  final bool available;
  final String? message;
}

class ConfigurationReportRepository implements ReportRepository {
  const ConfigurationReportRepository();

  @override
  Future<PilotReport> load() async => const PilotReport(
        enrolled: 0,
        attempts: 0,
        unknownRate: 0,
        available: false,
        message: 'Iniciá sesión y configurá un piloto para consultar métricas reales.',
      );
}

class HttpReportRepository implements ReportRepository {
  HttpReportRepository(this.baseUri, this.accessToken);

  final Uri baseUri;
  final String accessToken;

  @override
  Future<PilotReport> load() async {
    final client = HttpClient();
    try {
      final request = await client.getUrl(baseUri);
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $accessToken');
      final response = await request.close();
      final body = jsonDecode(await response.transform(utf8.decoder).join()) as Map<String, dynamic>;
      if (response.statusCode >= 400) throw HttpException('Report request failed', uri: baseUri);
      final attempts = body['attempts'] as Map<String, dynamic>;
      final participation = body['participation'] as Map<String, dynamic>;
      return PilotReport(
        enrolled: participation['enrolled'] as int,
        attempts: attempts['total'] as int,
        unknownRate: (attempts['unknown_rate'] as num).toDouble(),
      );
    } finally {
      client.close();
    }
  }
}

abstract interface class ReportRepository {
  Future<PilotReport> load();
}

class InMemoryReportRepository implements ReportRepository {
  const InMemoryReportRepository();
  @override
  Future<PilotReport> load() async => const PilotReport(enrolled: 0, attempts: 0, unknownRate: 0);
}
