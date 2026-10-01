import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import 'auth_service.dart';

class AppSession {
  const AppSession({
    required this.baseUrl,
    this.accessToken = '',
    this.refreshToken = '',
    this.email = '',
    this.password = '',
    this.institutionId,
    this.cohortId,
    this.memberships = const [],
    this.userEmail,
  });

  final String baseUrl;
  final String accessToken;
  final String refreshToken;
  final String email;
  final String password;
  final int? institutionId;
  final int? cohortId;
  final List<InstitutionMembership> memberships;
  final String? userEmail;

  bool get authenticated =>
      baseUrl.trim().isNotEmpty && accessToken.trim().isNotEmpty;
  bool get mvpReady =>
      authenticated && institutionId != null && cohortId != null;

  factory AppSession.fromEnvironment() => AppSession(
    baseUrl: const String.fromEnvironment(
      'DUALSIGN_API_BASE_URL',
      defaultValue: 'http://10.0.2.2:8080/api/',
    ),
    accessToken: const String.fromEnvironment('DUALSIGN_ACCESS_TOKEN'),
    email: const String.fromEnvironment('DUALSIGN_EMAIL'),
    password: const String.fromEnvironment('DUALSIGN_PASSWORD'),
    institutionId: int.tryParse(
      const String.fromEnvironment('DUALSIGN_INSTITUTION_ID'),
    ),
    cohortId: int.tryParse(const String.fromEnvironment('DUALSIGN_COHORT_ID')),
  );

  Future<AppSession?> bootstrap({
    http.Client? client,
    SessionStorage? storage,
  }) async {
    if (baseUrl.trim().isEmpty) return null;
    final auth = AuthRepository(
      baseUrl: baseUrl,
      storage: storage ?? const _UnavailableStorage(),
      client: client,
    );
    var token = accessToken;
    var refresh = refreshToken;
    var configuredInstitutionId = institutionId;
    if (token.trim().isEmpty && email.trim().isEmpty && password.isEmpty) {
      final stored = await auth.storedTokens();
      token = stored?.access ?? '';
      refresh = stored?.refresh ?? '';
    }
    if (token.trim().isEmpty && (email.trim().isEmpty || password.isEmpty))
      return null;
    final httpClient = client ?? http.Client();
    try {
      if (token.trim().isEmpty) {
        final pair = await auth.login(email, password);
        token = pair.access;
        refresh = pair.refresh;
      }
      var me = await _me(httpClient, token);
      if (me.statusCode == 401 && refresh.isNotEmpty) {
        final pair = await auth.refresh(refresh);
        token = pair.access;
        refresh = pair.refresh;
        me = await _me(httpClient, token);
      }
      if (me.statusCode >= 400)
        throw SessionException('Your session has expired. Please sign in again.');
      final body = jsonDecode(me.body) as Map<String, dynamic>;
      final memberships = (body['memberships'] as List<dynamic>? ?? [])
          .cast<Map<String, dynamic>>();
      if (!memberships.any((item) => item['institution_id'] == configuredInstitutionId))
        configuredInstitutionId = null;
      return AppSession(
        baseUrl: baseUrl,
        accessToken: token,
        refreshToken: refresh,
        institutionId: configuredInstitutionId,
        cohortId: cohortId,
        memberships: memberships
            .map(InstitutionMembership.fromJson)
            .toList(growable: false),
        userEmail: (body['user'] as Map<String, dynamic>?)?['email'] as String?,
      );
    } finally {
      if (client == null) httpClient.close();
    }
  }

  Future<http.Response> _me(http.Client client, String token) => client.get(
    Uri.parse(baseUrl).resolve('mobile/me'),
    headers: {'Authorization': 'Bearer $token'},
  );
}

class InstitutionMembership {
  const InstitutionMembership({
    required this.institutionId,
    required this.institutionName,
    required this.role,
  });

  final int institutionId;
  final String institutionName;
  final String role;

  factory InstitutionMembership.fromJson(Map<String, dynamic> json) =>
      InstitutionMembership(
        institutionId: json['institution_id'] as int,
        institutionName: json['institution_name'] as String,
        role: json['role'] as String,
      );
}

class _UnavailableStorage implements SessionStorage {
  const _UnavailableStorage();
  @override
  Future<String?> read(String key) async => null;
  @override
  Future<void> write(String key, String value) async {}
  @override
  Future<void> delete(String key) async {}
}

final appSessionProvider = Provider<AppSession>(
  (ref) => AppSession.fromEnvironment(),
);
final sessionBootstrapProvider = FutureProvider<AppSession?>(
  (ref) => ref.read(appSessionProvider).bootstrap(
    storage: ref.read(sessionStorageProvider),
  ),
);

class SessionException implements Exception {
  const SessionException(this.message);
  final String message;

  @override
  String toString() => message;
}
