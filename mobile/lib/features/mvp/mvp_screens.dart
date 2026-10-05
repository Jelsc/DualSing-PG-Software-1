import 'package:flutter/material.dart';

import 'communication_repository.dart';
import 'mvp_repositories.dart';
import 'practice_repository.dart';
import 'report_repository.dart';

class CommunicationScreen extends StatefulWidget {
  const CommunicationScreen({
    super.key,
    required this.repository,
    required this.playback,
  });
  final CommunicationRepository repository;
  final Playback playback;

  @override
  State<CommunicationScreen> createState() => _CommunicationScreenState();
}

class _CommunicationScreenState extends State<CommunicationScreen> {
  final input = TextEditingController();
  CommunicationResult? result;
  String? error;
  bool loading = false;

  Future<void> resolve() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final value = await widget.repository.resolve(input.text);
      if (mounted) setState(() => result = value);
    } catch (_) {
      if (mounted) setState(() => error = 'No se pudo consultar el catálogo.');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  void dispose() {
    input.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(24),
    child: ListView(
      children: [
        Text('Comunicar', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 8),
        const Text(
          'Usá una intención o alias controlado. No es traducción libre.',
        ),
        const SizedBox(height: 20),
        TextField(
          controller: input,
          decoration: const InputDecoration(
            labelText: 'Intención o alias controlado',
            hintText: 'Ej.: hello',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 12),
        FilledButton(
          onPressed: loading ? null : resolve,
          child: Text(loading ? 'Consultando...' : 'Resolver'),
        ),
        if (error != null)
          Padding(padding: const EdgeInsets.only(top: 16), child: Text(error!)),
        if (result != null)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Controlled resolution: ${result!.status}',
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                  if (result!.reason != null)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      child: Text(result!.reason!),
                    ),
                  for (final step in result!.steps)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(step.gloss),
                      subtitle: Text(
                        'clip_key: ${step.clipKey} · ${step.assetAvailable ? 'asset available' : 'playback unavailable'}',
                      ),
                    ),
                  if (result!.steps.any((step) => !step.assetAvailable))
                    const Padding(
                      padding: EdgeInsets.only(top: 8),
                      child: Text(
                        'Playback unavailable: this synthetic pilot has no avatar assets.',
                      ),
                    ),
                  if (result!.steps.any((step) => step.assetAvailable))
                    OutlinedButton.icon(
                      onPressed: () => widget.playback.play(result!.steps),
                      icon: const Icon(Icons.replay),
                      label: const Text('Reproducir de nuevo'),
                    ),
                ],
              ),
            ),
          ),
      ],
    ),
  );
}

class PracticeScreen extends StatefulWidget {
  const PracticeScreen({super.key, required this.repository, this.consent});
  final PracticeRepository repository;
  final Future<void> Function(String action)? consent;

  @override
  State<PracticeScreen> createState() => _PracticeScreenState();
}

class _PracticeScreenState extends State<PracticeScreen> {
  PracticeActivity? activity;
  List<PracticeActivity> activities = [];
  bool consentConfirmed = false;
  PracticeResult? result;
  String selectedResult = 'unknown';
  String? error;
  bool loading = true;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final rows = await widget.repository.listActivities();
      if (mounted)
        setState(() {
          activities = rows;
          activity = rows.isEmpty ? null : rows.first;
          loading = false;
        });
    } catch (_) {
      if (mounted)
        setState(() {
          loading = false;
          error = 'No se pudieron cargar las actividades validadas.';
        });
    }
  }

  Future<void> submit() async {
    if (activity == null) return;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final value = await widget.repository.submit(activity!, selectedResult);
      if (mounted) setState(() => result = value);
    } catch (_) {
      if (mounted) setState(() => error = 'No se pudo registrar el intento.');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> recordConsent(bool granted) async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      await widget.consent!(granted ? 'grant' : 'withdraw');
      if (mounted) setState(() => consentConfirmed = granted);
    } catch (_) {
      if (mounted)
        setState(
          () => error =
              'No se pudo guardar el consentimiento. Inténtalo de nuevo.',
        );
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (loading && activity == null)
      return const Center(child: CircularProgressIndicator());
    if (activity == null)
      return Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              error ??
                  'No hay actividades validadas para la institución configurada.',
            ),
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: load,
              child: const Text('Volver a cargar'),
            ),
          ],
        ),
      );
    return Padding(
      padding: const EdgeInsets.all(24),
      child: ListView(
        children: [
          Text('Practicar', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          DropdownButtonFormField<int>(
            initialValue: activity!.id,
            decoration: const InputDecoration(labelText: 'Actividad'),
            isExpanded: true,
            items: activities
                .map(
                  (item) => DropdownMenuItem(
                    value: item.id,
                    child: Text(item.prompt, overflow: TextOverflow.ellipsis),
                  ),
                )
                .toList(),
            onChanged: loading
                ? null
                : (id) => setState(() {
                    activity = activities.firstWhere((item) => item.id == id);
                    result = null;
                    error = null;
                    selectedResult = 'unknown';
                  }),
          ),
          Text(activity!.prompt),
          Text('Manual/synthetic evaluation · model ${activity!.modelVersion}'),
          const SizedBox(height: 16),
          DropdownButtonFormField<String>(
            key: ValueKey(activity!.id),
            value: selectedResult,
            decoration: const InputDecoration(labelText: 'Manual result'),
            items: const [
              DropdownMenuItem(value: 'correct', child: Text('Correct')),
              DropdownMenuItem(value: 'incorrect', child: Text('Incorrect')),
              DropdownMenuItem(value: 'unknown', child: Text('Unknown')),
            ],
            onChanged: loading
                ? null
                : (value) => setState(() => selectedResult = value!),
          ),
          const SizedBox(height: 12),
          if (widget.consent != null) ...[
            const Text(
              'Consentimiento de práctica piloto · v1. Se guardarán tus resultados manuales asociados a tu cuenta para el seguimiento del piloto. Esta práctica sintética no captura cámara, audio ni gestos reales.',
            ),
            CheckboxListTile(
              value: consentConfirmed,
              title: const Text(
                'Autorizo el registro de mis resultados de práctica',
              ),
              subtitle: const Text(
                'Desmarca para registrar la revocación del consentimiento.',
              ),
              onChanged: loading ? null : (value) => recordConsent(value!),
            ),
          ],
          FilledButton(
            onPressed: loading || (widget.consent != null && !consentConfirmed)
                ? null
                : submit,
            child: Text(loading ? 'Submitting...' : 'Submit manual result'),
          ),
          if (error != null)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(error!),
            ),
          if (result != null)
            Card(
              child: ListTile(
                title: Text('Server result: ${result!.value.toUpperCase()}'),
                subtitle: Text(
                  'Latency: ${result!.latencyMs ?? 'not reported'} ms · model ${activity!.modelVersion} · ${result!.evaluationMode} · ${result!.inferenceSource}',
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class ProgressScreen extends StatefulWidget {
  const ProgressScreen({
    super.key,
    required this.repository,
    required this.enrollment,
  });
  final ReportRepository repository;
  final PilotEnrollmentRepository enrollment;

  @override
  State<ProgressScreen> createState() => _ProgressScreenState();
}

class _ProgressScreenState extends State<ProgressScreen> {
  late Future<PilotReport> report;
  String? enrollmentMessage;

  @override
  void initState() {
    super.initState();
    report = widget.repository.load();
  }

  Future<void> enroll() async {
    try {
      final value = await widget.enrollment.enroll();
      if (mounted)
        setState(
          () => enrollmentMessage = value.enrolled
              ? 'Enrolled in cohort ${value.cohortId}.'
              : 'Enrollment was not completed.',
        );
    } catch (_) {
      if (mounted)
        setState(
          () => enrollmentMessage = 'Enrollment could not be completed.',
        );
    }
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<PilotReport>(
    future: report,
    builder: (context, snapshot) {
      if (snapshot.connectionState == ConnectionState.waiting)
        return const Center(child: CircularProgressIndicator());
      if (snapshot.hasError)
        return const Padding(
          padding: EdgeInsets.all(24),
          child: Text('No se pudo cargar el progreso.'),
        );
      if (!snapshot.hasData)
        return const Padding(
          padding: EdgeInsets.all(24),
          child: Text('El progreso no está disponible.'),
        );
      final value = snapshot.data!;
      if (!value.available)
        return Padding(
          padding: const EdgeInsets.all(24),
          child: Text(value.message ?? 'Las métricas no están disponibles.'),
        );
      return Padding(
        padding: const EdgeInsets.all(24),
        child: ListView(
          children: [
            Text('Progreso', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 8),
            const Text('Aggregate pilot report · safe when empty'),
            const SizedBox(height: 16),
            Text('Participants: ${value.enrolled}'),
            Text('Completion: ${value.completion}%'),
            Text('Attempts: ${value.attempts}'),
            Text(
              'Correct / incorrect / unknown: ${value.correct} / ${value.incorrect} / ${value.unknown}',
            ),
            Text(
              'Latency p50 / p95: ${value.p50Latency ?? 'n/a'} / ${value.p95Latency ?? 'n/a'} ms',
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: enroll,
              child: const Text('Enroll in pilot cohort'),
            ),
            if (enrollmentMessage != null)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(enrollmentMessage!),
              ),
            const SizedBox(height: 16),
            const Text(
              'Los resultados son descriptivos y no prueban eficacia clínica o educativa.',
            ),
          ],
        ),
      );
    },
  );
}
