# Logging

- Log once per operation, at the outcome - not "starting X" plus "X succeeded".
- Success logs go at debug unless someone operating the service needs them.
- Errors are logged once, where they are handled, with the IDs needed to investigate.
- Don't log and rethrow the same error at every layer.

```ts
// no
logger.debug('Publishing orders.created event');
await publish(event);
logger.log('orders.created event published successfully');
// yes
await publish(event);
logger.debug('published orders.created', { eventId });
```
