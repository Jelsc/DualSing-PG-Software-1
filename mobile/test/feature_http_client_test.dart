import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:dualsign_mobile/auth_service.dart';
import 'package:dualsign_mobile/feature_http_client.dart';

class MemoryStorage implements SessionStorage {
  final values = <String, String>{};
  @override
  Future<String?> read(String key) async => values[key];
  @override
  Future<void> write(String key, String value) async {
    values[key] = value;
  }

  @override
  Future<void> delete(String key) async {
    values.remove(key);
  }
}

void main() {
  final base = Uri.parse('https://api.test/api/');
  const tokens = TokenPair(access: 'old', refresh: 'refresh-old');

  test(
    'concurrent 401s share refresh, persist rotation and replay bodies once',
    () async {
      final storage = MemoryStorage();
      var refreshes = 0;
      var oldRequests = 0;
      var retries = 0;
      final bothFailed = Completer<void>();
      final network = MockClient((request) async {
        if (request.url.path.endsWith('/refresh')) {
          refreshes++;
          await bothFailed.future;
          return http.Response(
            jsonEncode({'access': 'new', 'refresh': 'refresh-new'}),
            200,
          );
        }
        expect(request.body, '{"result":"unknown"}');
        expect(request.followRedirects, isFalse);
        if (request.headers['Authorization'] == 'Bearer old') {
          if (++oldRequests == 2) bothFailed.complete();
          return http.Response('{}', 401);
        }
        expect(request.headers['Authorization'], 'Bearer new');
        retries++;
        return http.Response('{}', 200);
      });
      final auth = AuthRepository(
        baseUrl: base.toString(),
        storage: storage,
        client: network,
      );
      final client = FeatureHttpClient(
        baseUri: base,
        auth: auth,
        tokens: tokens,
        client: network,
      );
      final results = await Future.wait(
        List.generate(
          2,
          (_) => client.post(
            base.resolve('mobile/attempt'),
            body: '{"result":"unknown"}',
          ),
        ),
      );
      expect(results.map((r) => r.statusCode), [200, 200]);
      expect(refreshes, 1);
      expect(retries, 2);
      expect((await auth.storedTokens())!.refresh, 'refresh-new');
    },
  );

  test('a retried 401 is returned without a second refresh', () async {
    var refreshes = 0;
    var features = 0;
    final network = MockClient((request) async {
      if (request.url.path.endsWith('/refresh')) {
        refreshes++;
        return http.Response('{"access":"new","refresh":"rotated"}', 200);
      }
      features++;
      return http.Response('{}', 401);
    });
    final auth = AuthRepository(
      baseUrl: base.toString(),
      storage: MemoryStorage(),
      client: network,
    );
    final client = FeatureHttpClient(
      baseUri: base,
      auth: auth,
      tokens: tokens,
      client: network,
    );
    expect((await client.get(base.resolve('mobile/me'))).statusCode, 401);
    expect(refreshes, 1);
    expect(features, 2);
  });

  test('logout wins against an in-flight refresh and prevents retry', () async {
    final started = Completer<void>();
    final response = Completer<http.Response>();
    var features = 0;
    final network = MockClient((request) async {
      if (request.url.path.endsWith('/refresh')) {
        started.complete();
        return response.future;
      }
      features++;
      return http.Response('{}', 401);
    });
    final auth = AuthRepository(
      baseUrl: base.toString(),
      storage: MemoryStorage(),
      client: network,
    );
    final client = FeatureHttpClient(
      baseUri: base,
      auth: auth,
      tokens: tokens,
      client: network,
    );
    final pending = client.get(base.resolve('mobile/me'));
    final assertion = expectLater(pending, throwsA(isA<AuthException>()));
    await started.future;
    await auth.logout();
    response.complete(
      http.Response('{"access":"new","refresh":"rotated"}', 200),
    );
    await assertion;
    expect(await auth.storedTokens(), isNull);
    expect(features, 1);
  });

  for (final status in [401, 503]) {
    test(
      'refresh $status stops replay and only rejection clears storage',
      () async {
        final storage = MemoryStorage();
        await storage.write(AuthRepository.accessKey, 'old');
        await storage.write(AuthRepository.refreshKey, 'refresh-old');
        var features = 0;
        final network = MockClient((request) async {
          if (request.url.path.endsWith('/refresh'))
            return http.Response('{}', status);
          features++;
          return http.Response('{}', 401);
        });
        final auth = AuthRepository(
          baseUrl: base.toString(),
          storage: storage,
          client: network,
        );
        final client = FeatureHttpClient(
          baseUri: base,
          auth: auth,
          tokens: tokens,
          client: network,
        );
        await expectLater(
          client.get(base.resolve('mobile/me')),
          throwsA(isA<AuthException>()),
        );
        expect(features, 1);
        expect(await auth.storedTokens(), status == 401 ? isNull : isNotNull);
      },
    );
  }

  test(
    'network failure preserves refresh token and permits a later retry',
    () async {
      final storage = MemoryStorage();
      await storage.write(AuthRepository.accessKey, 'old');
      await storage.write(AuthRepository.refreshKey, 'refresh-old');
      final network = MockClient((request) async {
        if (request.url.path.endsWith('/refresh'))
          throw http.ClientException('offline');
        return http.Response('{}', 401);
      });
      final auth = AuthRepository(
        baseUrl: base.toString(),
        storage: storage,
        client: network,
      );
      final client = FeatureHttpClient(
        baseUri: base,
        auth: auth,
        tokens: tokens,
        client: network,
      );
      await expectLater(
        client.get(base.resolve('mobile/me')),
        throwsA(isA<http.ClientException>()),
      );
      expect((await auth.storedTokens())!.refresh, 'refresh-old');
    },
  );

  test(
    'foreign origins and neighboring API paths never receive credentials',
    () async {
      var calls = 0;
      final network = MockClient((_) async {
        calls++;
        return http.Response('{}', 200);
      });
      final auth = AuthRepository(
        baseUrl: base.toString(),
        storage: MemoryStorage(),
        client: network,
      );
      final client = FeatureHttpClient(
        baseUri: base,
        auth: auth,
        tokens: tokens,
        client: network,
      );
      for (final url in [
        'https://evil.test/api/me',
        'https://api.test/api-other/me',
        'http://api.test/api/me',
      ]) {
        await expectLater(
          client.get(Uri.parse(url)),
          throwsA(isA<http.ClientException>()),
        );
      }
      expect(calls, 0);
    },
  );
}
