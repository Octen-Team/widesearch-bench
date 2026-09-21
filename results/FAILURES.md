# Recorded run failures

Errors are retained as zero-F1 attempts for every configuration. Failed usage is unknown; elapsed time is retained from the recorded failure duration. No selective reruns were used.

| Task | Configuration | Error | Elapsed seconds |
|---|---|---|---:|
| ws-0122 | Octen broad_search | JSONDecodeError: Expecting value: line 1 column 1 (char 0) | 45.052 |
| ws-0128 | Exa-instant | HTTPStatusError: Client error '400 Bad Request' for url 'https://api.openai.com/v1/chat/completions' | 60.569 |
| ws-0215 | Parallel-turbo | ConnectError: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1082) | 66.990 |
| ws-0231 | Exa-instant | ConnectError: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1082) | 18.176 |
| ws-0279 | Parallel-turbo | HTTPStatusError: Server error '520 <none>' for url 'https://api.openai.com/v1/chat/completions' | 32.541 |
