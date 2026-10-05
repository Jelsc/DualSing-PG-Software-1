import 'dart:convert';

import 'package:http/http.dart' as http;

import 'communication_repository.dart';
import 'practice_repository.dart';
import 'report_repository.dart';

class PilotEnrollment {
  const PilotEnrollment({required this.cohortId, required this.enrolled});
  final int cohortId;
  final bool enrolled;
}

abstract interface class PilotEnrollmentRepository {
  Future<PilotEnrollment> enroll();
}

class HttpPilotEnrollmentRepository implements PilotEnrollmentRepository {
  HttpPilotEnrollmentRepository(
    this.baseUri,
    this.accessToken, {
    http.Client? client,
  }) : _client = client ?? http.Client();
  final Uri baseUri;
  final String accessToken;
  final http.Client _client;

  @override
  Future<PilotEnrollment> enroll() async {
    final response = await _client.post(
      baseUri,
      headers: {'Authorization': 'Bearer $accessToken'},
    );
    if (response.statusCode >= 400)
      throw http.ClientException(
        'Pilot enrollment failed (${response.statusCode})',
      );
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return PilotEnrollment(
      cohortId: body['cohort_id'] as int,
      enrolled: body['enrolled'] as bool,
    );
  }
}

class MvpRepositories {
  const MvpRepositories({
    required this.communication,
    required this.practice,
    required this.report,
    required this.enrollment,
    this.consent,
  });
  final CommunicationRepository communication;
  final PracticeRepository practice;
  final ReportRepository report;
  final PilotEnrollmentRepository enrollment;
  final Future<void> Function(String action)? consent;

  factory MvpRepositories.http(
    Uri baseUri,
    String token, {
    required int institutionId,
    required int cohortId,
    http.Client? client,
  }) {
    final root = baseUri.resolve('mobile/mvp/$institutionId/');
    return MvpRepositories(
      consent: (action) async {
        final response = await (client ?? http.Client()).post(
          baseUri.resolve('mobile/consents'),
          headers: {
            'Authorization': 'Bearer $token',
            'Content-Type': 'application/json',
          },
          body: jsonEncode({
            'purpose': 'pilot_practice',
            'policy_version': 'v1',
            'action': action,
          }),
        );
        if (response.statusCode >= 400)
          throw http.ClientException('Consent could not be recorded.');
      },
      communication: HttpCommunicationRepository(
        root.resolve('communication/resolve'),
        token,
        client: client,
      ),
      practice: HttpPracticeRepository(
        root.resolve('practice/'),
        token,
        client: client,
      ),
      report: HttpReportRepository(
        root.resolve('pilots/$cohortId/report'),
        token,
        client: client,
      ),
      enrollment: HttpPilotEnrollmentRepository(
        root.resolve('pilots/$cohortId/participants'),
        token,
        client: client,
      ),
    );
  }
}

class UnauthenticatedMvpRepositories extends MvpRepositories {
  const UnauthenticatedMvpRepositories()
    : super(
        communication: const ConfigurationCommunicationRepository(),
        practice: const ConfigurationPracticeRepository(),
        report: const ConfigurationReportRepository(),
        enrollment: const ConfigurationPilotEnrollmentRepository(),
      );
}

class ConfigurationPilotEnrollmentRepository
    implements PilotEnrollmentRepository {
  const ConfigurationPilotEnrollmentRepository();

  @override
  Future<PilotEnrollment> enroll() =>
      throw StateError('Authentication is required to enroll in a pilot.');
}
