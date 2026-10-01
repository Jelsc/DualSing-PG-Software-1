import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:dualsign_mobile/app_session.dart';
import 'package:dualsign_mobile/features/mvp/cohort_repository.dart';
import 'package:dualsign_mobile/features/mvp/mvp_repositories.dart';
import 'package:dualsign_mobile/features/workspace/workspace_state.dart';

void main() {
  test('does not require institution or cohort environment defaults', () {
    final session = AppSession.fromEnvironment();
    expect(session.institutionId, isNull);
    expect(session.cohortId, isNull);
  });

  test('requires an institution when multiple memberships exist', () async {
    final container = _container(
      const AppSession(
        baseUrl: 'https://api.test/api/',
        accessToken: 'access',
        memberships: [
          InstitutionMembership(
            institutionId: 1,
            institutionName: 'One',
            role: 'operator',
          ),
          InstitutionMembership(
            institutionId: 2,
            institutionName: 'Two',
            role: 'operator',
          ),
        ],
      ),
      _FakeCohorts({
        1: const [],
        2: [_cohort(20)],
      }),
    );
    addTearDown(container.dispose);

    final initial = await container.read(pilotSelectionProvider.future);
    expect(initial.status, PilotSelectionStatus.institutionRequired);
    await container.read(pilotSelectionProvider.notifier).selectInstitution(2);
    expect(container.read(pilotSelectionProvider).value!.institutionId, 2);
    expect(container.read(pilotSelectionProvider).value!.cohortId, 20);
  });

  test('selection scopes repositories to the selected server IDs', () async {
    final session = const AppSession(
      baseUrl: 'https://api.test/api/',
      accessToken: 'access',
      memberships: [
        InstitutionMembership(
          institutionId: 7,
          institutionName: 'Seven',
          role: 'operator',
        ),
      ],
    );
    final container = _container(
      session,
      _FakeCohorts({
        7: [_cohort(9)],
      }),
    );
    addTearDown(container.dispose);

    await container.read(pilotSelectionProvider.future);
    final repositories = container.read(mvpRepositoriesProvider);
    expect(repositories, isA<MvpRepositories>());
    expect(repositories, isNot(isA<UnauthenticatedMvpRepositories>()));
  });

  test('keeps no membership and no cohort states explicit', () async {
    final noMembership = _container(
      const AppSession(baseUrl: 'https://api.test/api/', accessToken: 'access'),
      _FakeCohorts({}),
    );
    addTearDown(noMembership.dispose);
    expect(
      (await noMembership.read(pilotSelectionProvider.future)).status,
      PilotSelectionStatus.noMembership,
    );

    final noCohorts = _container(
      const AppSession(
        baseUrl: 'https://api.test/api/',
        accessToken: 'access',
        memberships: [
          InstitutionMembership(
            institutionId: 1,
            institutionName: 'One',
            role: 'operator',
          ),
        ],
      ),
      _FakeCohorts({1: const []}),
    );
    addTearDown(noCohorts.dispose);
    expect(
      (await noCohorts.read(pilotSelectionProvider.future)).status,
      PilotSelectionStatus.noCohorts,
    );
  });
}

ProviderContainer _container(AppSession session, CohortRepository repository) {
  return ProviderContainer(
    overrides: [
      sessionBootstrapProvider.overrideWith((ref) async => session),
      cohortRepositoryProvider.overrideWithValue(repository),
    ],
  );
}

PilotCohort _cohort(int id) => PilotCohort(
  id: id,
  name: 'Cohort $id',
  startDate: DateTime(2026),
  endDate: null,
  status: 'planned',
  consentRequired: true,
  enrolled: false,
);

class _FakeCohorts implements CohortRepository {
  _FakeCohorts(this.byInstitution);
  final Map<int, List<PilotCohort>> byInstitution;

  @override
  Future<List<PilotCohort>> list(int institutionId) async =>
      byInstitution[institutionId] ?? const [];
}
