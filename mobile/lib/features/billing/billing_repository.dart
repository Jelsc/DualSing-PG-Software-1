import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';

import '../../app_session.dart';

class BillingStatus {
  const BillingStatus({required this.origin, this.subscriptionStatus});

  final String origin;
  final String? subscriptionStatus;

  factory BillingStatus.fromJson(Map<String, dynamic> json) => BillingStatus(
    origin: json['origin'] as String? ?? 'free',
    subscriptionStatus: json['subscription_status'] as String?,
  );
}

class BillingRepository {
  BillingRepository({
    required this.baseUrl,
    required this.accessToken,
    http.Client? client,
  }) : _client = client ?? http.Client();

  final String baseUrl;
  final String accessToken;
  final http.Client _client;

  Future<BillingStatus> status() async {
    final response = await _client.get(
      Uri.parse('$baseUrl/mobile/billing/status'),
      headers: {'Authorization': 'Bearer $accessToken'},
    );
    if (response.statusCode != 200)
      throw Exception('No se pudo consultar el estado de facturación.');
    return BillingStatus.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<BillingStatus> startPlusCheckout() async {
    final response = await _client.post(
      Uri.parse('$baseUrl/mobile/billing/plus/checkout'),
      headers: {'Authorization': 'Bearer $accessToken'},
    );
    if (response.statusCode != 200)
      throw Exception('Plus no está disponible en este entorno.');
    final url =
        (jsonDecode(response.body) as Map<String, dynamic>)['checkout_url']
            as String;
    if (!await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication))
      throw Exception('No se pudo abrir Stripe Checkout.');
    return status();
  }
}

final billingRepositoryProvider = Provider<BillingRepository?>((ref) {
  final session = ref.watch(appSessionProvider);
  if (!session.authenticated) return null;
  return BillingRepository(
    baseUrl: session.baseUrl,
    accessToken: session.accessToken,
  );
});
