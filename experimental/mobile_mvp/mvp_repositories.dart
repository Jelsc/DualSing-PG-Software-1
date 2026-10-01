import 'communication_repository.dart';
import 'practice_repository.dart';
import 'report_repository.dart';

class MvpRepositories {
  const MvpRepositories({
    required this.communication,
    required this.practice,
    required this.report,
  });

  final CommunicationRepository communication;
  final PracticeRepository practice;
  final ReportRepository report;
}

class UnauthenticatedMvpRepositories extends MvpRepositories {
  const UnauthenticatedMvpRepositories()
      : super(
          communication: const ConfigurationCommunicationRepository(),
          practice: const ConfigurationPracticeRepository(),
          report: const ConfigurationReportRepository(),
        );

  factory UnauthenticatedMvpRepositories.http(
    Uri baseUri,
    String token, {
    required int cohortId,
  }) {
    return MvpRepositories(
      communication: HttpCommunicationRepository(
        baseUri.resolve('communication/resolve'),
        token,
      ),
      practice: HttpPracticeRepository(baseUri.resolve('practice/'), token),
      report: HttpReportRepository(
        baseUri.resolve('pilots/$cohortId/report'),
        token,
      ),
    );
  }
}

class DemoMvpRepositories extends MvpRepositories {
  const DemoMvpRepositories()
      : super(
          communication: const InMemoryCommunicationRepository(),
          practice: const InMemoryPracticeRepository(),
          report: const InMemoryReportRepository(),
        );
}
