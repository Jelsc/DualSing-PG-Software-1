import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

abstract interface class SessionStorage {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
  Future<void> delete(String key);
}

class SecureSessionStorage implements SessionStorage {
  SecureSessionStorage({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  @override
  Future<String?> read(String key) => _storage.read(key: key);

  @override
  Future<void> write(String key, String value) =>
      _storage.write(key: key, value: value);

  @override
  Future<void> delete(String key) => _storage.delete(key: key);
}

class TokenPair {
  const TokenPair({required this.access, required this.refresh});

  final String access;
  final String refresh;

  factory TokenPair.fromJson(Map<String, dynamic> json) {
    final access = json['access'];
    final refresh = json['refresh'];
    if (access is! String || refresh is! String ||
        access.trim().isEmpty || refresh.trim().isEmpty) {
      throw const AuthException('The server returned an invalid session.');
    }
    return TokenPair(access: access, refresh: refresh);
  }
}

class AuthRepository {
  AuthRepository({
    required this.baseUrl,
    required SessionStorage storage,
    http.Client? client,
  }) : _storage = storage,
       _client = client ?? http.Client();

  static const accessKey = 'dualsign.access_token';
  static const refreshKey = 'dualsign.refresh_token';
  static const emailKey = 'dualsign.session_email';

  final String baseUrl;
  final SessionStorage _storage;
  final http.Client _client;

  Future<TokenPair> login(String email, String password) async {
    final pair = await _requestToken(
      'mobile/token',
      {'email': email.trim(), 'password': password},
    );
    await _persist(pair, email.trim().toLowerCase());
    return pair;
  }

  Future<TokenPair> register(
    String email,
    String password,
    String confirmation,
  ) async {
    final pair = await _requestToken(
      'mobile/register',
      {
        'email': email.trim(),
        'password': password,
        'password_confirmation': confirmation,
      },
    );
    await _persist(pair, email.trim().toLowerCase());
    return pair;
  }

  Future<TokenPair?> storedTokens() async {
    final access = await _storage.read(accessKey);
    final refresh = await _storage.read(refreshKey);
    if (access == null || refresh == null || access.isEmpty || refresh.isEmpty)
      return null;
    return TokenPair(access: access, refresh: refresh);
  }

  Future<String?> storedEmail() => _storage.read(emailKey);

  Future<TokenPair> refresh(String refreshToken) async {
    final pair = await _requestToken(
      'mobile/token/refresh',
      {'refresh': refreshToken},
    );
    await _persist(pair, await storedEmail());
    return pair;
  }

  Future<void> logout({String? refreshToken}) async {
    try {
      if (refreshToken != null && refreshToken.isNotEmpty) {
        await _client.post(
          _uri('mobile/token/revoke'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'refresh': refreshToken}),
        );
      }
    } finally {
      await Future.wait([
        _storage.delete(accessKey),
        _storage.delete(refreshKey),
        _storage.delete(emailKey),
      ]);
    }
  }

  Future<TokenPair> _requestToken(String path, Map<String, String> payload) async {
    final response = await _client.post(
      _uri(path),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );
    if (response.statusCode >= 400) throw _mapError(response);
    return TokenPair.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<void> _persist(TokenPair pair, String? email) async {
    await _storage.write(accessKey, pair.access);
    await _storage.write(refreshKey, pair.refresh);
    if (email != null && email.isNotEmpty) await _storage.write(emailKey, email);
  }

  Uri _uri(String path) => Uri.parse(baseUrl).resolve(path);

  AuthException _mapError(http.Response response) {
    var message = 'The request could not be completed.';
    try {
      final body = jsonDecode(response.body);
      if (body is Map<String, dynamic> && body['detail'] is String)
        message = body['detail'] as String;
    } catch (_) {
      // Keep a stable user-facing error when the server does not return JSON.
    }
    return AuthException(switch (response.statusCode) {
      401 => 'Email or password is incorrect.',
      409 => 'An account with that email already exists.',
      422 => message,
      _ => 'The authentication service is unavailable. Try again later.',
    });
  }
}

class AuthException implements Exception {
  const AuthException(this.message);
  final String message;

  @override
  String toString() => message;
}

final sessionStorageProvider = Provider<SessionStorage>(
  (ref) => SecureSessionStorage(),
);
