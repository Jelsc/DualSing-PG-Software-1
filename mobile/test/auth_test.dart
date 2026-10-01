import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:dualsign_mobile/app.dart';
import 'package:dualsign_mobile/app_session.dart';
import 'package:dualsign_mobile/auth_service.dart';
import 'package:dualsign_mobile/features/auth/auth_screens.dart';

void main() {
  test('secure session storage persists only session values and clears them', () async {
    final storage = _FakeStorage();
    final repository = AuthRepository(
      baseUrl: 'https://api.test/api/',
      storage: storage,
      client: _FakeClient(),
    );

    await repository.login('USER@example.test', 'correct-password');
    expect(await storage.read(AuthRepository.accessKey), 'access-token');
    expect(await storage.read(AuthRepository.refreshKey), 'refresh-token');
    expect(await storage.read(AuthRepository.emailKey), 'user@example.test');
    expect(storage.values.values, isNot(contains('correct-password')));

    await repository.logout(refreshToken: 'refresh-token');
    expect(await repository.storedTokens(), isNull);
    expect(await storage.read(AuthRepository.emailKey), isNull);
  });

  testWidgets('login shows validation and authenticates successfully', (tester) async {
    final auth = _FakeAuthRepository();
    await tester.pumpWidget(_providerApp(auth, const AuthScreen()));
    await tester.tap(find.text('Sign in'));
    await tester.pump();
    expect(find.text('Enter a valid email address.'), findsOneWidget);

    await tester.enterText(find.byType(TextFormField).at(0), 'user@example.test');
    await tester.enterText(find.byType(TextFormField).at(1), 'correct-password');
    await tester.tap(find.text('Sign in'));
    await tester.pumpAndSettle();
    expect(auth.loginCalled, isTrue);
  });

  testWidgets('login displays server failure', (tester) async {
    final auth = _FakeAuthRepository()..loginError = const AuthException('Email or password is incorrect.');
    await tester.pumpWidget(_providerApp(auth, const AuthScreen()));
    await tester.enterText(find.byType(TextFormField).at(0), 'user@example.test');
    await tester.enterText(find.byType(TextFormField).at(1), 'correct-password');
    await tester.tap(find.text('Sign in'));
    await tester.pumpAndSettle();
    expect(find.text('Email or password is incorrect.'), findsOneWidget);
  });

  testWidgets('registration validates confirmation and succeeds', (tester) async {
    final auth = _FakeAuthRepository();
    await tester.pumpWidget(_providerApp(auth, const AuthScreen()));
    await tester.tap(find.text('Create a personal account'));
    await tester.pumpAndSettle();
    final submit = find.byType(FilledButton);
    await tester.ensureVisible(submit);
    await tester.tap(submit);
    await tester.pump();
    expect(find.text('Enter a valid email address.'), findsOneWidget);

    await tester.enterText(find.byType(TextFormField).at(0), 'user@example.test');
    await tester.enterText(find.byType(TextFormField).at(1), 'correct-password');
    await tester.enterText(find.byType(TextFormField).at(2), 'different-password');
    await tester.ensureVisible(submit);
    await tester.tap(submit);
    await tester.pump();
    expect(find.text('Passwords do not match.'), findsOneWidget);
    await tester.enterText(find.byType(TextFormField).at(2), 'correct-password');
    await tester.ensureVisible(submit);
    await tester.tap(submit);
    await tester.pumpAndSettle();
    expect(auth.registerCalled, isTrue);
  });

  testWidgets('unauthenticated startup never shows workspace data', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [sessionBootstrapProvider.overrideWith((ref) async => null)],
        child: const DualSignMobileApp(),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Welcome back'), findsOneWidget);
    expect(find.text('Practice'), findsNothing);
  });
}

Widget _providerApp(AuthRepository auth, Widget child) => ProviderScope(
  overrides: [
    authRepositoryProvider.overrideWithValue(auth),
    sessionBootstrapProvider.overrideWith((ref) async => null),
  ],
  child: MaterialApp(home: child),
);

class _FakeStorage implements SessionStorage {
  final values = <String, String>{};
  @override
  Future<String?> read(String key) async => values[key];
  @override
  Future<void> write(String key, String value) async => values[key] = value;
  @override
  Future<void> delete(String key) async => values.remove(key);
}

class _FakeClient extends http.BaseClient {
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final body = request.method == 'POST'
        ? '{"access":"access-token","refresh":"refresh-token","token_type":"Bearer"}'
        : '{}';
    return http.StreamedResponse(Stream.value(body.codeUnits), 200);
  }
}

class _FakeAuthRepository extends AuthRepository {
  _FakeAuthRepository()
    : super(baseUrl: 'https://api.test/api/', storage: _FakeStorage());

  bool loginCalled = false;
  bool registerCalled = false;
  AuthException? loginError;

  @override
  Future<TokenPair> login(String email, String password) async {
    if (loginError != null) throw loginError!;
    loginCalled = true;
    return const TokenPair(access: 'access', refresh: 'refresh');
  }

  @override
  Future<TokenPair> register(String email, String password, String confirmation) async {
    registerCalled = true;
    return const TokenPair(access: 'access', refresh: 'refresh');
  }
}
