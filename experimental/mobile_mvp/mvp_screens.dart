import 'package:flutter/material.dart';

import 'communication_repository.dart';
import 'practice_repository.dart';
import 'report_repository.dart';

class CommunicationScreen extends StatefulWidget {
  const CommunicationScreen({super.key, required this.repository, required this.playback});
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
    setState(() { loading = true; error = null; });
    try { result = await widget.repository.resolve(input.text); } catch (_) { error = 'No se pudo consultar el catálogo.'; }
    if (mounted) setState(() => loading = false);
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(24),
    child: ListView(children: [
       Text('Comunicar', style: Theme.of(context).textTheme.headlineSmall),
       const SizedBox(height: 8),
       const Text('Usá una intención o alias controlado. No es traducción libre.'),
       if (widget.repository is ConfigurationCommunicationRepository)
         const Padding(
           padding: EdgeInsets.only(top: 8),
           child: Text('Comunicación de producción requiere sesión e institución configuradas.'),
         ),
      const SizedBox(height: 20),
       TextField(controller: input, decoration: const InputDecoration(labelText: 'Intención o alias controlado', hintText: 'Ej.: hello', border: OutlineInputBorder())),
      const SizedBox(height: 12),
      FilledButton(onPressed: loading ? null : resolve, child: Text(loading ? 'Consultando...' : 'Resolver')),
      if (error != null) Padding(padding: const EdgeInsets.only(top: 16), child: Text(error!, semanticsLabel: error!)),
      if (result != null) _CommunicationResult(result: result!, onReplay: () => widget.playback.play(result!.steps)),
    ]),
  );
}

class _CommunicationResult extends StatelessWidget {
  const _CommunicationResult({required this.result, required this.onReplay});
  final CommunicationResult result;
  final VoidCallback onReplay;
  @override
  Widget build(BuildContext context) => Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text(result.status, style: const TextStyle(fontWeight: FontWeight.bold)),
    if (result.reason != null) Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: Text(result.reason!)),
    for (final step in result.steps) ListTile(contentPadding: EdgeInsets.zero, title: Text(step.gloss), subtitle: Text('${step.clipKey} · asset unavailable')),
    if (result.steps.isNotEmpty) OutlinedButton.icon(onPressed: onReplay, icon: const Icon(Icons.replay), label: const Text('Reproducir de nuevo')),
  ])));
}

class PracticeScreen extends StatefulWidget {
  const PracticeScreen({super.key, required this.repository});
  final PracticeRepository repository;
  @override
  State<PracticeScreen> createState() => _PracticeScreenState();
}

class _PracticeScreenState extends State<PracticeScreen> {
  PracticeActivity? activity;
  PracticeResult? result;
  bool loading = true;
  @override
  void initState() { super.initState(); load(); }
  Future<void> load() async { final rows = await widget.repository.listActivities(); if (mounted) setState(() { activity = rows.isEmpty ? null : rows.first; loading = false; }); }
  Future<void> submit() async { if (activity == null) return; setState(() => loading = true); final value = await widget.repository.submit(activity!); if (mounted) setState(() { result = value; loading = false; }); }
  @override
  Widget build(BuildContext context) => Padding(padding: const EdgeInsets.all(24), child: loading ? const Center(child: CircularProgressIndicator()) : activity == null ? Text(widget.repository is ConfigurationPracticeRepository ? 'Práctica de producción requiere sesión e institución configuradas.' : 'No hay actividades validadas.') : ListView(children: [Text('Practicar', style: Theme.of(context).textTheme.headlineSmall), const SizedBox(height: 8), Text(activity!.prompt), Text('Modo scaffold · ${activity!.modelVersion}'), const SizedBox(height: 16), FilledButton(onPressed: submit, child: const Text('Registrar intento')), if (result != null) Card(child: ListTile(title: Text(result!.value.toUpperCase()), subtitle: Text(result!.explanation)),), if (result?.value == 'unknown') const Text('UNKNOWN no es un error: la confianza fue insuficiente.') ]));
}

class ProgressScreen extends StatelessWidget {
  const ProgressScreen({super.key, required this.repository});
  final ReportRepository repository;
  @override
  Widget build(BuildContext context) => FutureBuilder<PilotReport>(future: repository.load(), builder: (context, snapshot) { if (!snapshot.hasData) return const Center(child: CircularProgressIndicator()); final report = snapshot.data!; if (!report.available) return Padding(padding: const EdgeInsets.all(24), child: Text(report.message ?? 'Las métricas no están disponibles.')); return Padding(padding: const EdgeInsets.all(24), child: ListView(children: [Text('Progreso', style: Theme.of(context).textTheme.headlineSmall), const SizedBox(height: 16), Text('Piloto agregado, sin PII'), Text('Participantes elegibles: ${report.enrolled}'), Text('Intentos: ${report.attempts}'), Text('UNKNOWN: ${(report.unknownRate * 100).toStringAsFixed(0)}%'), const SizedBox(height: 16), const Text('Los resultados son descriptivos y no prueban eficacia clínica o educativa.') ])); });
}
