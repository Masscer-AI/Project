Subscriptions testing

1. Sync Subscriptions 

```bash
./taskfile shell
```

```bash
python manage.py sync_subscription_plans
```

2. Sync Organization Subscriptions

```bash
./taskfile shell
```

```bash
python manage.py sync_organization_subscriptions
```

3. Sync 

```bash
stripe listen --forward-to localhost/v1/payments/webhook/
```
