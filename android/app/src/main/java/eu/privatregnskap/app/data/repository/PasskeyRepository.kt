package eu.privatregnskap.app.data.repository

import eu.privatregnskap.app.data.network.ApiService
import eu.privatregnskap.app.data.network.dto.PasskeyCredentialResponse
import eu.privatregnskap.app.data.network.dto.PasskeyRegisterBeginRequest
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import javax.inject.Inject
import javax.inject.Singleton

interface PasskeyRepository {
    suspend fun listCredentials(): Result<List<PasskeyCredentialResponse>>
    suspend fun deleteCredential(id: Int): Result<Unit>
    suspend fun renameCredential(id: Int, newName: String): Result<PasskeyCredentialResponse>
    suspend fun registerBegin(credentialName: String?): Result<String>
    suspend fun registerComplete(registrationJson: String, optionsJson: String): Result<Unit>
}

@Singleton
class PasskeyRepositoryImpl @Inject constructor(
    private val apiService: ApiService
) : PasskeyRepository {

    override suspend fun listCredentials(): Result<List<PasskeyCredentialResponse>> =
        runCatching { apiService.listPasskeyCredentials() }

    override suspend fun deleteCredential(id: Int): Result<Unit> =
        runCatching {
            apiService.deletePasskeyCredential(id)
            Unit
        }

    override suspend fun renameCredential(id: Int, newName: String): Result<PasskeyCredentialResponse> =
        runCatching { apiService.renamePasskeyCredential(id, newName) }

    override suspend fun registerBegin(credentialName: String?): Result<String> =
        runCatching {
            val response = apiService.passkeyRegisterBegin(PasskeyRegisterBeginRequest(credentialName))
            response.string()
        }

    override suspend fun registerComplete(registrationJson: String, optionsJson: String): Result<Unit> =
        runCatching {
            val attestationObj = JSONObject(registrationJson)
            val challengeKey = JSONObject(optionsJson).optString("challenge_key", "")
            if (challengeKey.isNotEmpty()) {
                attestationObj.put("challenge_key", challengeKey)
            }
            val requestObj = JSONObject()
            requestObj.put("attestation", attestationObj)
            val body = requestObj.toString().toRequestBody("application/json".toMediaType())
            apiService.passkeyRegisterComplete(body)
            Unit
        }
}
