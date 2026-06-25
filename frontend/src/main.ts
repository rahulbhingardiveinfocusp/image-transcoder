import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig, awsConfig } from './app/app.config';
import { App } from './app/app';
import { Amplify } from 'aws-amplify';

Amplify.configure(awsConfig);
bootstrapApplication(App, appConfig)
  .catch((err) => console.error(err));