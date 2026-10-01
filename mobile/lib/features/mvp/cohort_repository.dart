import 'dart:convert';

import 'package:http/http.dart' as http;

class PilotCohort {
  const PilotCohort({
    required this.id,
    required this.name,
    required this.startDate,
    required this.endDate,
    required this.status,
    required this.consentRequired,
    required this.enrolled,
  });

  final int id;
  final String name;
  final DateTime startDate;
  final DateTime? endDate;
  final String status;
  final bool consentRequired;
  final bool enrolled;

  factory PilotCohort.fromJson(Map<String, dynamic> json) => PilotCohort(
    id: json['id'] as int,
    name: json['name'] as String,
    startDate: DateTime.parse(json['start_date'] as String),
    endDate: (json['end_date'] as String?) == null
        ? null
        : DateTime.parse(json['end_date'] as String),
    status: json['status'] as String,
    consentRequired: json['consent_required'] as bool,
    enrolled: json['enrolled'] as bool,
  );
}

abstract interface class CohortRepository {
  Future<List<PilotCohort>> list(int institutionId);
}

class HttpCohortRepository implements CohortRepository {
  HttpCohortRepository(this.baseUri, this.accessToken, {http.Client? client})
    : _client = client ?? http.Client();

  final Uri baseUri;
  final String accessToken;
  final http.Client _client;

  @override
  Future<List<PilotCohort>> list(int institutionId) async {
    final response = await _client.get(
      baseUri.resolve('mobile/mvp/$institutionId/pilots/cohorts'),
      headers: {'Authorization': 'Bearer $accessToken'},
    );
    if (response.statusCode >= 400) {
      throw http.ClientException(
        'Cohort request failed (${response.statusCode})',
      );
    }
    return (jsonDecode(response.body) as List<dynamic>)
        .cast<Map<String, dynamic>>()
        .map(PilotCohort.fromJson)
        .toList(growable: false);
  }
}
