import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { UnifiedHttpExceptionFilter } from './common/http-exception.filter';
import { REQUEST_ID_HEADER, normalizeRequestId } from './common/request-id';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.use(
    (
      req: { headers: Record<string, string | string[] | undefined> },
      res: { setHeader: (name: string, value: string) => void },
      next: () => void,
    ) => {
    const requestId = normalizeRequestId(req.headers[REQUEST_ID_HEADER]);
    req.headers[REQUEST_ID_HEADER] = requestId;
    res.setHeader(REQUEST_ID_HEADER, requestId);
    next();
    },
  );
  app.useGlobalFilters(new UnifiedHttpExceptionFilter());
  const host = process.env.HOST ?? '0.0.0.0';
  const port = Number(process.env.PORT ?? 3001);
  await app.listen(port, host);
}

void bootstrap();
