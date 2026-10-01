import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app_session.dart';
import '../../auth_service.dart';

class AuthScreen extends ConsumerStatefulWidget {
  const AuthScreen({super.key, this.initialError});

  final String? initialError;

  @override
  ConsumerState<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends ConsumerState<AuthScreen> {
  bool _registering = false;

  @override
  Widget build(BuildContext context) {
    return _registering
        ? RegistrationScreen(
            initialError: widget.initialError,
            onLogin: () => setState(() => _registering = false),
          )
        : LoginScreen(
            initialError: widget.initialError,
            onRegister: () => setState(() => _registering = true),
          );
  }
}

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key, this.initialError, required this.onRegister});

  final String? initialError;
  final VoidCallback onRegister;

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() { _busy = true; _error = null; });
    try {
      await ref.read(authRepositoryProvider).login(_email.text, _password.text);
      ref.invalidate(sessionBootstrapProvider);
    } on AuthException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AuthScaffold(
    title: 'Welcome back',
    subtitle: 'Sign in to continue to your DualSign workspace.',
    form: Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          EmailField(controller: _email),
          const SizedBox(height: 14),
          PasswordField(controller: _password, label: 'Password'),
          if (_error ?? widget.initialError case final message?) ...[
            const SizedBox(height: 14),
            ErrorMessage(message: message),
          ],
          const SizedBox(height: 22),
          FilledButton(
            onPressed: _busy ? null : _submit,
            child: _busy ? const ButtonProgress() : const Text('Sign in'),
          ),
          TextButton(
            onPressed: _busy ? null : widget.onRegister,
            child: const Text('Create a personal account'),
          ),
        ],
      ),
    ),
  );
}

class RegistrationScreen extends ConsumerStatefulWidget {
  const RegistrationScreen({super.key, this.initialError, required this.onLogin});

  final String? initialError;
  final VoidCallback onLogin;

  @override
  ConsumerState<RegistrationScreen> createState() => _RegistrationScreenState();
}

class _RegistrationScreenState extends ConsumerState<RegistrationScreen> {
  final _formKey = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _confirmation = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _confirmation.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() { _busy = true; _error = null; });
    try {
      await ref.read(authRepositoryProvider).register(
        _email.text,
        _password.text,
        _confirmation.text,
      );
      ref.invalidate(sessionBootstrapProvider);
    } on AuthException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AuthScaffold(
    title: 'Create your account',
    subtitle: 'Registration creates a personal account only. Institution access is granted separately.',
    form: Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          EmailField(controller: _email),
          const SizedBox(height: 14),
          PasswordField(controller: _password, label: 'Password'),
          const SizedBox(height: 14),
          PasswordField(
            controller: _confirmation,
            label: 'Confirm password',
            validator: (value) => value != _password.text ? 'Passwords do not match.' : null,
          ),
          if (_error ?? widget.initialError case final message?) ...[
            const SizedBox(height: 14),
            ErrorMessage(message: message),
          ],
          const SizedBox(height: 22),
          FilledButton(
            onPressed: _busy ? null : _submit,
            child: _busy ? const ButtonProgress() : const Text('Create account'),
          ),
          TextButton(
            onPressed: _busy ? null : widget.onLogin,
            child: const Text('Already have an account? Sign in'),
          ),
        ],
      ),
    ),
  );
}

class AuthScaffold extends StatelessWidget {
  const AuthScaffold({required this.title, required this.subtitle, required this.form, super.key});
  final String title;
  final String subtitle;
  final Widget form;

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(28),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Icon(Icons.sign_language, size: 42),
                    const SizedBox(height: 18),
                    Text('DualSign', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 10),
                    Text(title, style: Theme.of(context).textTheme.headlineSmall),
                    const SizedBox(height: 8),
                    Text(subtitle),
                    const SizedBox(height: 26),
                    form,
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  );
}

class EmailField extends StatelessWidget {
  const EmailField({required this.controller, super.key});
  final TextEditingController controller;

  @override
  Widget build(BuildContext context) => TextFormField(
    controller: controller,
    keyboardType: TextInputType.emailAddress,
    textInputAction: TextInputAction.next,
    autocorrect: false,
    decoration: const InputDecoration(labelText: 'Email address'),
    validator: (value) {
      final email = value?.trim() ?? '';
      if (email.isEmpty || !email.contains('@')) return 'Enter a valid email address.';
      return null;
    },
  );
}

class PasswordField extends StatelessWidget {
  const PasswordField({required this.controller, required this.label, this.validator, super.key});
  final TextEditingController controller;
  final String label;
  final String? Function(String?)? validator;

  @override
  Widget build(BuildContext context) => TextFormField(
    controller: controller,
    obscureText: true,
    decoration: InputDecoration(labelText: label),
    validator: validator ?? (value) => (value ?? '').length < 8 ? 'Use at least 8 characters.' : null,
  );
}

class ErrorMessage extends StatelessWidget {
  const ErrorMessage({required this.message, super.key});
  final String message;
  @override
  Widget build(BuildContext context) => Text(
    message,
    style: TextStyle(color: Theme.of(context).colorScheme.error),
  );
}

class ButtonProgress extends StatelessWidget {
  const ButtonProgress({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox(
    width: 18,
    height: 18,
    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
  );
}

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  final config = ref.watch(appSessionProvider);
  return AuthRepository(
    baseUrl: config.baseUrl,
    storage: ref.watch(sessionStorageProvider),
  );
});
