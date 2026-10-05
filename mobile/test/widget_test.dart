import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:dualsign_mobile/app.dart';
import 'package:dualsign_mobile/app_session.dart';
import 'package:dualsign_mobile/features/mvp/communication_repository.dart';
import 'package:dualsign_mobile/features/mvp/cohort_repository.dart';
import 'package:dualsign_mobile/features/mvp/mvp_repositories.dart';
import 'package:dualsign_mobile/features/mvp/practice_repository.dart';
import 'package:dualsign_mobile/features/mvp/report_repository.dart';
import 'package:dualsign_mobile/features/workspace/app_section.dart';
import 'package:dualsign_mobile/features/workspace/workspace_state.dart';
import 'package:dualsign_mobile/features/mvp/mvp_screens.dart';
import 'package:dualsign_mobile/features/billing/billing_repository.dart';

void main() {
  testWidgets('single membership can switch cohorts on a narrow screen', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final container = ProviderContainer(
      overrides: [
        sessionBootstrapProvider.overrideWith(
          (ref) async => const AppSession(
            baseUrl: 'https://api.test/api/',
            accessToken: 'jwt',
            cohortId: 9,
            memberships: [
              InstitutionMembership(
                institutionId: 7,
                institutionName: 'One institution',
                role: 'operator',
              ),
            ],
          ),
        ),
        cohortRepositoryProvider.overrideWithValue(_MultipleCohorts()),
      ],
    );
    addTearDown(container.dispose);
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const DualSignMobileApp(),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byType(DropdownButton<int>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Second cohort').last);
    await tester.pumpAndSettle();
    expect(container.read(pilotSelectionProvider).valueOrNull!.cohortId, 10);
    expect(tester.takeException(), isNull);
  });
  testWidgets('personal account can reach Profile without membership', (
    tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sessionBootstrapProvider.overrideWith(
            (ref) async => const AppSession(
              baseUrl: 'https://api.test/api/',
              accessToken: 'jwt',
            ),
          ),
          billingRepositoryProvider.overrideWithValue(null),
        ],
        child: const DualSignMobileApp(),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Personal workspace'), findsOneWidget);
    await tester.tap(find.text(AppSection.profile.label).last);
    await tester.pumpAndSettle();
    expect(find.text('Tu información personal'), findsOneWidget);
    expect(find.text('Sign out'), findsOneWidget);
  });

  testWidgets(
    'practice selects another activity and records explicit grant and withdrawal',
    (tester) async {
      final actions = <String>[];
      final practice = _SelectablePractice();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: PracticeScreen(
              repository: practice,
              consent: (action) async {
                actions.add(action);
              },
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(
        tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
        isNull,
      );
      await tester.tap(find.byType(DropdownButtonFormField<int>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('SECOND').last);
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.byType(CheckboxListTile));
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pumpAndSettle();
      expect(actions, ['grant']);
      await tester.ensureVisible(find.byType(FilledButton));
      await tester.tap(find.byType(FilledButton));
      await tester.pumpAndSettle();
      expect(practice.submitted, 2);
      await tester.ensureVisible(find.byType(CheckboxListTile));
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pumpAndSettle();
      expect(actions, ['grant', 'withdraw']);
      expect(
        tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
        isNull,
      );
    },
  );

  testWidgets('shows an explicit unauthenticated state', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [sessionBootstrapProvider.overrideWith((ref) async => null)],
        child: const DualSignMobileApp(),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Welcome back'), findsOneWidget);
    expect(find.text('Create a personal account'), findsOneWidget);
  });

  testWidgets('shows configured session and MVP result states', (tester) async {
    final repositories = MvpRepositories(
      communication: _FakeCommunication(),
      practice: _FakePractice(),
      report: _FakeReport(),
      enrollment: _FakeEnrollment(),
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sessionBootstrapProvider.overrideWith(
            (ref) async => const AppSession(
              baseUrl: 'https://api.test/api/',
              accessToken: 'jwt',
              institutionId: 7,
              cohortId: 9,
              memberships: [
                InstitutionMembership(
                  institutionId: 7,
                  institutionName: 'Pilot institution',
                  role: 'operator',
                ),
              ],
            ),
          ),
          cohortRepositoryProvider.overrideWithValue(_FakeCohorts()),
          mvpRepositoriesProvider.overrideWithValue(repositories),
        ],
        child: const DualSignMobileApp(),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text(AppSection.practice.label).last);
    await tester.pumpAndSettle();
    expect(
      find.text('Manual/synthetic evaluation · model synthetic-v1'),
      findsOneWidget,
    );
    await tester.tap(find.byType(DropdownButtonFormField<String>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Correct').last);
    await tester.pumpAndSettle();
    final submitButton = find.byType(FilledButton).last;
    await tester.ensureVisible(submitButton);
    await tester.tap(submitButton);
    await tester.pumpAndSettle();
    expect(find.textContaining('Server result: CORRECT'), findsOneWidget);

    await tester.tap(find.text(AppSection.progress.label).last);
    await tester.pumpAndSettle();
    expect(
      find.text('Correct / incorrect / unknown: 1 / 0 / 0'),
      findsOneWidget,
    );
    expect(find.text('Enroll in pilot cohort'), findsOneWidget);

    await tester.tap(find.text(AppSection.communicate.label).last);
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'hello');
    await tester.tap(find.text('Resolver'));
    await tester.pumpAndSettle();
    expect(find.textContaining('clip_key: sign:greet-v1'), findsOneWidget);
    expect(find.textContaining('playback unavailable'), findsOneWidget);
  });

  testWidgets('keeps navigation visible while session is loading', (
    tester,
  ) async {
    final pendingSession = Completer<AppSession?>();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sessionBootstrapProvider.overrideWith((ref) => pendingSession.future),
        ],
        child: const DualSignMobileApp(),
      ),
    );
    expect(find.text('Connecting securely'), findsOneWidget);
  });
}

class _FakeCommunication implements CommunicationRepository {
  @override
  Future<CommunicationResult> resolve(String input) async =>
      const CommunicationResult(
        status: 'missing_clip_mapping',
        steps: [
          CommunicationStep(
            signId: 'greet-v1',
            clipKey: 'sign:greet-v1',
            assetAvailable: false,
            gloss: 'HELLO',
          ),
        ],
      );
}

class _FakePractice implements PracticeRepository {
  @override
  Future<List<PracticeActivity>> listActivities() async => const [
    PracticeActivity(
      id: 1,
      prompt: 'HELLO',
      signId: 'greet-v1',
      modelVersion: 'synthetic-v1',
    ),
  ];

  @override
  Future<PracticeResult> submit(
    PracticeActivity activity,
    String result, {
    int? latencyMs,
  }) async => PracticeResult(
    value: result,
    latencyMs: 42,
    evaluationMode: 'synthetic_scaffold',
    inferenceSource: 'controlled_client',
  );
}

class _SelectablePractice extends _FakePractice {
  int? submitted;
  @override
  Future<List<PracticeActivity>> listActivities() async => [
    ...(await super.listActivities()),
    const PracticeActivity(
      id: 2,
      prompt: 'SECOND',
      signId: 'second',
      modelVersion: 'synthetic-v1',
    ),
  ];
  @override
  Future<PracticeResult> submit(
    PracticeActivity activity,
    String result, {
    int? latencyMs,
  }) {
    submitted = activity.id;
    return super.submit(activity, result, latencyMs: latencyMs);
  }
}

class _FakeReport implements ReportRepository {
  @override
  Future<PilotReport> load() async => const PilotReport(
    enrolled: 1,
    attempts: 1,
    correct: 1,
    incorrect: 0,
    unknown: 0,
    unknownRate: 0,
    completion: 100,
    p50Latency: 42,
    p95Latency: 42,
  );
}

class _FakeEnrollment implements PilotEnrollmentRepository {
  @override
  Future<PilotEnrollment> enroll() async =>
      const PilotEnrollment(cohortId: 9, enrolled: true);
}

class _FakeCohorts implements CohortRepository {
  @override
  Future<List<PilotCohort>> list(int institutionId) async => [
    PilotCohort(
      id: 9,
      name: 'Pilot cohort',
      startDate: DateTime(2026),
      endDate: null,
      status: 'planned',
      consentRequired: true,
      enrolled: false,
    ),
  ];
}

class _MultipleCohorts extends _FakeCohorts {
  @override
  Future<List<PilotCohort>> list(int institutionId) async => [
    ...(await super.list(institutionId)),
    PilotCohort(
      id: 10,
      name: 'Second cohort',
      startDate: DateTime(2026),
      endDate: null,
      status: 'planned',
      consentRequired: true,
      enrolled: false,
    ),
  ];
}
