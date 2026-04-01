package eu.privatregnskap.app.di

import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import eu.privatregnskap.app.data.repository.AuthRepository
import eu.privatregnskap.app.data.repository.AuthRepositoryImpl
import eu.privatregnskap.app.data.repository.TokenRepository
import eu.privatregnskap.app.data.repository.TokenRepositoryImpl
import eu.privatregnskap.app.data.repository.LedgerRepository
import eu.privatregnskap.app.data.repository.LedgerRepositoryImpl
import eu.privatregnskap.app.data.repository.AttachmentRepository
import eu.privatregnskap.app.data.repository.AttachmentRepositoryImpl
import eu.privatregnskap.app.data.repository.BudgetRepository
import eu.privatregnskap.app.data.repository.BudgetRepositoryImpl
import eu.privatregnskap.app.data.repository.PasskeyRepository
import eu.privatregnskap.app.data.repository.PasskeyRepositoryImpl
import eu.privatregnskap.app.data.repository.PostingQueueRepository
import eu.privatregnskap.app.data.repository.PostingQueueRepositoryImpl
import eu.privatregnskap.app.data.repository.TransactionRepository
import eu.privatregnskap.app.data.repository.TransactionRepositoryImpl
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class RepositoryModule {

    @Binds
    @Singleton
    abstract fun bindTokenRepository(impl: TokenRepositoryImpl): TokenRepository

    @Binds
    @Singleton
    abstract fun bindAuthRepository(impl: AuthRepositoryImpl): AuthRepository

    @Binds
    @Singleton
    abstract fun bindTransactionRepository(impl: TransactionRepositoryImpl): TransactionRepository

    @Binds
    @Singleton
    abstract fun bindLedgerRepository(impl: LedgerRepositoryImpl): LedgerRepository

    @Binds
    @Singleton
    abstract fun bindPostingQueueRepository(impl: PostingQueueRepositoryImpl): PostingQueueRepository

    @Binds
    @Singleton
    abstract fun bindPasskeyRepository(impl: PasskeyRepositoryImpl): PasskeyRepository

    @Binds
    @Singleton
    abstract fun bindAttachmentRepository(impl: AttachmentRepositoryImpl): AttachmentRepository

    @Binds
    @Singleton
    abstract fun bindBudgetRepository(impl: BudgetRepositoryImpl): BudgetRepository
}
