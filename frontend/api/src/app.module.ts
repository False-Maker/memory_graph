import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { sidecarClientProvider } from './sidecar/sidecar.provider';

@Module({
  imports: [],
  controllers: [AppController],
  providers: [AppService, sidecarClientProvider],
})
export class AppModule {}
