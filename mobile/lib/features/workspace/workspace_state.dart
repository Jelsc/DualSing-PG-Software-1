import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../mvp/mvp_repositories.dart';
import '../mvp/cohort_repository.dart';
import '../../app_session.dart';
import '../../auth_service.dart';
import '../../feature_http_client.dart';
import 'app_section.dart';

final selectedSectionProvider =
    NotifierProvider<SelectedSectionController, AppSection>(
      SelectedSectionController.new,
    );

class SelectedSectionController extends Notifier<AppSection> {
  @override
  AppSection build() => AppSection.learn;

  void select(AppSection section) => state = section;
}

/// The catalog stays empty until an approved course source is connected.
final learningMaterialsProvider = Provider<AsyncValue<List<LearningMaterial>>>((
  ref,
) {
  return const AsyncData([]);
});

final mvpRepositoriesProvider = Provider<MvpRepositories>((ref) {
  final selection = ref.watch(pilotSelectionProvider).valueOrNull;
  if (selection == null || !selection.ready)
    return const UnauthenticatedMvpRepositories();
  return MvpRepositories.http(
    Uri.parse(selection.session.baseUrl),
    selection.session.accessToken,
    institutionId: selection.institutionId!,
    cohortId: selection.cohortId!,
    client: ref.watch(featureHttpClientProvider),
  );
});

final cohortRepositoryProvider = Provider<CohortRepository>((ref) {
  final session = ref.watch(sessionBootstrapProvider).valueOrNull;
  if (session == null) return _UnavailableCohortRepository();
  return HttpCohortRepository(
    Uri.parse(session.baseUrl),
    session.accessToken,
    client: ref.watch(featureHttpClientProvider),
  );
});

final featureHttpClientProvider = Provider<FeatureHttpClient?>((ref) {
  final session = ref.watch(sessionBootstrapProvider).valueOrNull;
  if (session == null) return null;
  final client = FeatureHttpClient(
    baseUri: Uri.parse(session.baseUrl),
    auth: ref.watch(authRepositoryProvider),
    tokens: TokenPair(
      access: session.accessToken,
      refresh: session.refreshToken,
    ),
    onSessionExpired: () => ref.invalidate(sessionBootstrapProvider),
  );
  ref.onDispose(client.close);
  return client;
});

enum PilotSelectionStatus {
  unauthenticated,
  noMembership,
  institutionRequired,
  loadingCohorts,
  noCohorts,
  cohortRequired,
  ready,
}

class PilotSelection {
  const PilotSelection({
    required this.session,
    required this.memberships,
    required this.cohorts,
    required this.institutionId,
    required this.cohortId,
    required this.status,
  });

  final AppSession session;
  final List<InstitutionMembership> memberships;
  final List<PilotCohort> cohorts;
  final int? institutionId;
  final int? cohortId;
  final PilotSelectionStatus status;

  bool get ready => status == PilotSelectionStatus.ready;
}

final pilotSelectionProvider =
    AsyncNotifierProvider<PilotSelectionController, PilotSelection>(
      PilotSelectionController.new,
    );

class PilotSelectionController extends AsyncNotifier<PilotSelection> {
  @override
  Future<PilotSelection> build() async {
    final session = await ref.watch(sessionBootstrapProvider.future);
    if (session == null) return _emptySession();
    final memberships = session.memberships;
    if (memberships.isEmpty) {
      return PilotSelection(
        session: session,
        memberships: memberships,
        cohorts: const [],
        institutionId: null,
        cohortId: null,
        status: PilotSelectionStatus.noMembership,
      );
    }
    final institutionId = memberships.length == 1
        ? memberships.single.institutionId
        : null;
    if (institutionId == null) {
      return PilotSelection(
        session: session,
        memberships: memberships,
        cohorts: const [],
        institutionId: null,
        cohortId: null,
        status: PilotSelectionStatus.institutionRequired,
      );
    }
    return _loadCohorts(session, memberships, institutionId);
  }

  Future<void> selectInstitution(int institutionId) async {
    final current = state.valueOrNull;
    if (current == null ||
        !current.memberships.any(
          (item) => item.institutionId == institutionId,
        )) {
      return;
    }
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => _loadCohorts(current.session, current.memberships, institutionId),
    );
  }

  void selectCohort(int cohortId) {
    final current = state.valueOrNull;
    if (current == null || !current.cohorts.any((item) => item.id == cohortId))
      return;
    state = AsyncData(
      PilotSelection(
        session: current.session,
        memberships: current.memberships,
        cohorts: current.cohorts,
        institutionId: current.institutionId,
        cohortId: cohortId,
        status: PilotSelectionStatus.ready,
      ),
    );
  }

  Future<void> retry() async => ref.invalidateSelf();

  Future<PilotSelection> _loadCohorts(
    AppSession session,
    List<InstitutionMembership> memberships,
    int institutionId,
  ) async {
    final cohorts = await ref
        .read(cohortRepositoryProvider)
        .list(institutionId);
    final configured = cohorts.any((item) => item.id == session.cohortId);
    final cohortId = configured
        ? session.cohortId
        : cohorts.length == 1
        ? cohorts.single.id
        : null;
    return PilotSelection(
      session: session,
      memberships: memberships,
      cohorts: cohorts,
      institutionId: institutionId,
      cohortId: cohortId,
      status: cohorts.isEmpty
          ? PilotSelectionStatus.noCohorts
          : cohortId == null
          ? PilotSelectionStatus.cohortRequired
          : PilotSelectionStatus.ready,
    );
  }

  PilotSelection _emptySession() => PilotSelection(
    session: const AppSession(baseUrl: ''),
    memberships: const [],
    cohorts: const [],
    institutionId: null,
    cohortId: null,
    status: PilotSelectionStatus.unauthenticated,
  );
}

class LearningMaterial {
  const LearningMaterial();
}

class _UnavailableCohortRepository implements CohortRepository {
  @override
  Future<List<PilotCohort>> list(int institutionId) =>
      throw StateError('Authentication is required to load pilot cohorts.');
}
