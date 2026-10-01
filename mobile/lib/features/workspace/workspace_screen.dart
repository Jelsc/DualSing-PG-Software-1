import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../mvp/communication_repository.dart';
import '../mvp/mvp_screens.dart';
import '../billing/billing_repository.dart';
import '../auth/auth_screens.dart';
import '../../app_session.dart';
import 'app_section.dart';
import 'workspace_state.dart';

class WorkspaceScreen extends ConsumerWidget {
  const WorkspaceScreen({super.key});

  static const _wideLayoutBreakpoint = 720.0;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionBootstrapProvider);
    final section = ref.watch(selectedSectionProvider);
    final wideLayout =
        MediaQuery.sizeOf(context).width >= _wideLayoutBreakpoint;
    final content = session.when(
      loading: () => const _SessionState(
        message: 'Connecting securely to DualSign...',
        icon: Icons.sync,
      ),
      error: (error, _) => _SessionState(
        message: 'Could not authenticate this mobile session. $error',
        icon: Icons.lock_outline,
        error: true,
      ),
      data: (value) {
        if (value == null)
          return const SessionStatusScreen(
            title: 'Sign in required',
            message: 'Sign in to access your DualSign workspace.',
            icon: Icons.login_outlined,
          );
        final selection = ref.watch(pilotSelectionProvider);
        return selection.when(
          loading: () => const _SessionState(
            message: 'Loading your institutions and pilot cohorts...',
            icon: Icons.sync,
          ),
          error: (error, _) => _SelectionError(error: error.toString()),
          data: (selected) => switch (selected.status) {
            PilotSelectionStatus.unauthenticated => const SessionStatusScreen(
              title: 'Sign in required',
              message: 'Sign in to access your DualSign workspace.',
              icon: Icons.login_outlined,
            ),
            PilotSelectionStatus.noMembership => const SessionStatusScreen(
              title: 'Institution access pending',
              message:
                  'Your account is ready, but an authorized institution flow must grant membership before learning data is available.',
              icon: Icons.domain_disabled_outlined,
            ),
            PilotSelectionStatus.ready => _WorkspaceContent(section: section),
            _ => _PilotSelectionScreen(selection: selected),
          },
        );
      },
    );

    return Scaffold(
      body: SafeArea(
        child: Row(
          children: [
            if (wideLayout) _SectionRail(section: section, ref: ref),
            Expanded(
              child: Column(
                children: [
                  _WorkspaceHeader(section: section),
                  Expanded(
                    child: Center(
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 760),
                        child: content,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: wideLayout
          ? null
          : _SectionNavigationBar(section: section, ref: ref),
    );
  }
}

class _PilotSelectionScreen extends ConsumerWidget {
  const _PilotSelectionScreen({required this.selection});

  final PilotSelection selection;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final controller = ref.read(pilotSelectionProvider.notifier);
    final institutionRequired =
        selection.status == PilotSelectionStatus.institutionRequired;
    final noCohorts = selection.status == PilotSelectionStatus.noCohorts;
    final cohortRequired =
        selection.status == PilotSelectionStatus.cohortRequired;
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Choose your learning space',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),
              const Text(
                'Select an active institution membership, then choose an available pilot cohort.',
              ),
              const SizedBox(height: 24),
              DropdownButtonFormField<int>(
                value: selection.institutionId,
                decoration: const InputDecoration(labelText: 'Institution'),
                items: selection.memberships
                    .map(
                      (membership) => DropdownMenuItem<int>(
                        value: membership.institutionId,
                        child: Text(membership.institutionName),
                      ),
                    )
                    .toList(),
                onChanged:
                    institutionRequired || selection.institutionId != null
                    ? (id) {
                        if (id != null) controller.selectInstitution(id);
                      }
                    : null,
              ),
              if (selection.institutionId != null) ...[
                const SizedBox(height: 16),
                if (noCohorts)
                  const Text(
                    'No planned or active pilot cohorts are available for this institution.',
                  )
                else ...[
                  DropdownButtonFormField<int>(
                    value: selection.cohortId,
                    decoration: const InputDecoration(
                      labelText: 'Pilot cohort',
                    ),
                    items: selection.cohorts
                        .map(
                          (cohort) => DropdownMenuItem<int>(
                            value: cohort.id,
                            child: Text('${cohort.name} · ${cohort.status}'),
                          ),
                        )
                        .toList(),
                    onChanged: (id) {
                      if (id != null) controller.selectCohort(id);
                    },
                  ),
                  if (cohortRequired) ...[
                    const SizedBox(height: 8),
                    const Text('Choose a cohort to continue.'),
                  ],
                ],
              ],
              if (selection.status == PilotSelectionStatus.ready) ...[
                const SizedBox(height: 20),
                const Text('Workspace ready'),
                const SizedBox(height: 8),
                FilledButton(onPressed: () {}, child: const Text('Continue')),
              ],
              const SizedBox(height: 16),
              Align(
                alignment: Alignment.centerRight,
                child: SignOutButton(ref: ref),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SelectionError extends ConsumerWidget {
  const _SelectionError({required this.error});
  final String error;

  @override
  Widget build(BuildContext context, WidgetRef ref) => Column(
    mainAxisSize: MainAxisSize.min,
    children: [
      const Icon(Icons.cloud_off_outlined, size: 44),
      const SizedBox(height: 16),
      const Text('Could not load institution cohorts.'),
      const SizedBox(height: 8),
      Text(error, textAlign: TextAlign.center),
      const SizedBox(height: 16),
      FilledButton(
        onPressed: () => ref.invalidate(pilotSelectionProvider),
        child: const Text('Retry'),
      ),
    ],
  );
}

class _WorkspaceHeader extends ConsumerWidget {
  const _WorkspaceHeader({required this.section});

  final AppSection section;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final textTheme = Theme.of(context).textTheme;
    final selection = ref.watch(pilotSelectionProvider).valueOrNull;

    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 20, 24, 12),
      child: Row(
        children: [
          Semantics(
            label: 'DualSign, espacio de aprendizaje',
            child: const ExcludeSemantics(
              child: Icon(Icons.sign_language, size: 28),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('DualSign', style: textTheme.titleMedium),
                Text(
                  section.label,
                  style: textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w700,
                    letterSpacing: -0.5,
                  ),
                ),
              ],
            ),
          ),
          if (selection?.ready == true &&
              selection!.memberships.length > 1) ...[
            DropdownButton<int>(
              value: selection.institutionId,
              underline: const SizedBox.shrink(),
              items: selection.memberships
                  .map(
                    (membership) => DropdownMenuItem<int>(
                      value: membership.institutionId,
                      child: Text(membership.institutionName),
                    ),
                  )
                  .toList(),
              onChanged: (id) {
                if (id != null)
                  ref
                      .read(pilotSelectionProvider.notifier)
                      .selectInstitution(id);
              },
            ),
            if (selection.cohorts.length > 1)
              DropdownButton<int>(
                value: selection.cohortId,
                underline: const SizedBox.shrink(),
                items: selection.cohorts
                    .map(
                      (cohort) => DropdownMenuItem<int>(
                        value: cohort.id,
                        child: Text(cohort.name),
                      ),
                    )
                    .toList(),
                onChanged: (id) {
                  if (id != null)
                    ref.read(pilotSelectionProvider.notifier).selectCohort(id);
                },
              ),
          ],
        ],
      ),
    );
  }
}

class _WorkspaceContent extends ConsumerWidget {
  const _WorkspaceContent({required this.section});

  final AppSection section;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final materials = ref.watch(learningMaterialsProvider);
    final colors = Theme.of(context).colorScheme;
    final repositories = ref.watch(mvpRepositoriesProvider);

    if (section == AppSection.communicate) {
      return CommunicationScreen(
        repository: repositories.communication,
        playback: UnavailablePlayback(),
      );
    }
    if (section == AppSection.practice) {
      return PracticeScreen(repository: repositories.practice);
    }
    if (section == AppSection.progress) {
      return ProgressScreen(
        repository: repositories.report,
        enrollment: repositories.enrollment,
      );
    }
    if (section == AppSection.profile) {
      return const _ProfilePanel();
    }

    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 12, 24, 28),
      child: switch (materials) {
        AsyncData(:final value) when value.isEmpty => _EmptyState(
          section: section,
        ),
        AsyncData() => const _UnavailableState(
          message: 'Los materiales estarán disponibles más adelante.',
          icon: Icons.hourglass_empty,
        ),
        AsyncLoading() => const _LoadingState(),
        AsyncError() => _UnavailableState(
          message:
              'No se pudo cargar esta sección. Inténtalo de nuevo más tarde.',
          icon: Icons.cloud_off_outlined,
          color: colors.error,
        ),
        _ => const _LoadingState(),
      },
    );
  }
}

class _SessionState extends StatelessWidget {
  const _SessionState({
    required this.message,
    required this.icon,
    this.error = false,
  });
  final String message;
  final IconData icon;
  final bool error;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(24),
    child: Semantics(
      liveRegion: true,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            icon,
            size: 40,
            color: error ? Theme.of(context).colorScheme.error : null,
          ),
          const SizedBox(height: 16),
          Text(message, textAlign: TextAlign.center),
        ],
      ),
    ),
  );
}

class SessionStatusScreen extends ConsumerWidget {
  const SessionStatusScreen({
    required this.title,
    required this.message,
    required this.icon,
    super.key,
  });
  final String title;
  final String message;
  final IconData icon;

  @override
  Widget build(BuildContext context, WidgetRef ref) => Center(
    child: Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 44),
          const SizedBox(height: 16),
          Text(
            title,
            style: Theme.of(context).textTheme.titleLarge,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          Text(message, textAlign: TextAlign.center),
          const SizedBox(height: 20),
          SignOutButton(ref: ref),
        ],
      ),
    ),
  );
}

class SignOutButton extends StatelessWidget {
  const SignOutButton({required this.ref, super.key});
  final WidgetRef ref;

  @override
  Widget build(BuildContext context) => OutlinedButton.icon(
    onPressed: () async {
      final session = ref.read(sessionBootstrapProvider).valueOrNull;
      await ref
          .read(authRepositoryProvider)
          .logout(refreshToken: session?.refreshToken);
      ref.invalidate(pilotSelectionProvider);
      ref.invalidate(sessionBootstrapProvider);
    },
    icon: const Icon(Icons.logout),
    label: const Text('Sign out'),
  );
}

class _ProfilePanel extends ConsumerWidget {
  const _ProfilePanel();

  @override
  Widget build(BuildContext context, WidgetRef ref) => Column(
    children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(24, 24, 24, 0),
        child: Align(
          alignment: Alignment.centerLeft,
          child: SignOutButton(ref: ref),
        ),
      ),
      const Expanded(child: _ProfileBillingCard()),
    ],
  );
}

class _ProfileBillingCard extends ConsumerStatefulWidget {
  const _ProfileBillingCard();

  @override
  ConsumerState<_ProfileBillingCard> createState() =>
      _ProfileBillingCardState();
}

class _ProfileBillingCardState extends ConsumerState<_ProfileBillingCard>
    with WidgetsBindingObserver {
  Future<BillingStatus>? _statusFuture;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      final repository = ref.read(billingRepositoryProvider);
      if (repository != null && mounted)
        setState(() => _statusFuture = repository.status());
    }
  }

  @override
  Widget build(BuildContext context) {
    final repository = ref.watch(billingRepositoryProvider);
    final colors = Theme.of(context).colorScheme;
    if (repository == null) {
      return const Padding(
        padding: EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Tu información personal'),
            SizedBox(height: 8),
            Text(
              'La información de tu perfil aparecerá aquí cuando esté disponible.',
            ),
            SizedBox(height: 16),
            _UnavailableState(
              message:
                  'Configura una sesión autenticada para consultar tu plan.',
              icon: Icons.lock_outline,
            ),
          ],
        ),
      );
    }
    _statusFuture ??= repository.status();
    return FutureBuilder<BillingStatus>(
      future: _statusFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting)
          return const _LoadingState();
        if (snapshot.hasError)
          return _UnavailableState(
            message: 'No se pudo cargar tu estado de facturación.',
            icon: Icons.cloud_off_outlined,
            color: colors.error,
          );
        final status = snapshot.data!;
        final label = switch (status.origin) {
          'plus' => 'Plus',
          'enterprise_access' => 'Enterprise',
          _ => 'Free',
        };
        return Padding(
          padding: const EdgeInsets.all(24),
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Tu información personal',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 20),
                  Text(
                    'Tu plan',
                    style: Theme.of(context).textTheme.labelLarge,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    label,
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    label == 'Free'
                        ? 'Acceso básico. Mejorá a Plus con Stripe Checkout alojado.'
                        : 'El acceso efectivo lo confirma el servidor.',
                  ),
                  if (label == 'Free') ...[
                    const SizedBox(height: 20),
                    FilledButton(
                      onPressed: () async {
                        try {
                          final refreshed = await repository
                              .startPlusCheckout();
                          if (context.mounted)
                            setState(
                              () => _statusFuture = Future.value(refreshed),
                            );
                          if (context.mounted)
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text(
                                  'Estado actualizado desde el servidor.',
                                ),
                              ),
                            );
                        } catch (error) {
                          if (context.mounted)
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(content: Text(error.toString())),
                            );
                        }
                      },
                      child: const Text('Mejorar a Plus'),
                    ),
                  ],
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.section});

  final AppSection section;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Semantics(
      liveRegion: true,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
              color: colors.primaryContainer,
              borderRadius: BorderRadius.circular(20),
            ),
            alignment: Alignment.center,
            child: Icon(section.selectedIcon, size: 32, color: colors.primary),
          ),
          const SizedBox(height: 28),
          Text(
            section.description,
            style: textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          Text(
            section.emptyMessage,
            style: textTheme.bodyLarge?.copyWith(height: 1.5),
          ),
          const SizedBox(height: 20),
          Text(
            'Cuando haya contenido disponible, lo encontrarás aquí.',
            style: textTheme.bodyMedium?.copyWith(
              color: colors.onSurfaceVariant,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }
}

class _LoadingState extends StatelessWidget {
  const _LoadingState();

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Cargando materiales',
      liveRegion: true,
      child: Center(child: CircularProgressIndicator()),
    );
  }
}

class _UnavailableState extends StatelessWidget {
  const _UnavailableState({
    required this.message,
    required this.icon,
    this.color,
  });

  final String message;
  final IconData icon;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final foreground = color ?? Theme.of(context).colorScheme.onSurface;

    return Semantics(
      liveRegion: true,
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 36, color: foreground),
            const SizedBox(height: 16),
            Text(message, textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}

class _SectionNavigationBar extends StatelessWidget {
  const _SectionNavigationBar({required this.section, required this.ref});

  final AppSection section;
  final WidgetRef ref;

  @override
  Widget build(BuildContext context) {
    return NavigationBar(
      selectedIndex: section.index,
      onDestinationSelected: (index) => ref
          .read(selectedSectionProvider.notifier)
          .select(AppSection.values[index]),
      destinations: [
        for (final destination in AppSection.values)
          NavigationDestination(
            icon: Icon(destination.icon),
            selectedIcon: Icon(destination.selectedIcon),
            label: destination.label,
            tooltip: destination.description,
          ),
      ],
    );
  }
}

class _SectionRail extends StatelessWidget {
  const _SectionRail({required this.section, required this.ref});

  final AppSection section;
  final WidgetRef ref;

  @override
  Widget build(BuildContext context) {
    return NavigationRail(
      selectedIndex: section.index,
      labelType: NavigationRailLabelType.all,
      minWidth: 88,
      onDestinationSelected: (index) => ref
          .read(selectedSectionProvider.notifier)
          .select(AppSection.values[index]),
      destinations: [
        for (final destination in AppSection.values)
          NavigationRailDestination(
            icon: Icon(destination.icon),
            selectedIcon: Icon(destination.selectedIcon),
            label: Text(destination.label),
          ),
      ],
    );
  }
}
